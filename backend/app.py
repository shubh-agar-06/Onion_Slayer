import os
import threading
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from api.routes_analysis import analysis_bp
from api.routes_autonomous import autonomous_bp
from api.routes_entities import entities_bp
from api.routes_evolution import evolution_bp
from api.routes_export import export_bp
from api.routes_graph import graph_bp
from api.routes_infrastructure import infrastructure_bp
from api.routes_resolution import resolution_bp
from api.routes_search import search_bp
from api.routes_timeline import timeline_bp
from config import DEBUG, SERVER_HOST, SERVER_PORT
from database.connection import init_connection_pool
from core.logging import logger
from graph.graph_engine import NetworkXGraphEngine
from services.autonomous_collector import AutonomousCollector
from services.embedding_service import EmbeddingService
from services.infrastructure_service import InfrastructureService
from services.stylometric_service import StylometricEngine

_INITIALIZED = False
_INIT_LOCK = threading.Lock()


def startup():
    """Pre-flight warmup: initialize DB pool, build NetworkX graph, load stylometric signatures, and start autonomous collector."""
    global _INITIALIZED
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        logger.info("Initializing CTI Platform backend services in background...")
        try:
            init_connection_pool()
            NetworkXGraphEngine.build_graph()
            vendor_limit = int(os.environ.get("VENDOR_LIMIT", "150"))
            StylometricEngine.initialize_from_csv(max_vendors=vendor_limit)
            InfrastructureService.initialize_from_json()
            AutonomousCollector.get_instance().start()
            _INITIALIZED = True
            logger.info("CTI Platform backend initialization complete.")
        except Exception as exc:
            logger.error("Failed during backend warmup: %s", exc)


def create_app() -> Flask:
    """Assemble and configure the Flask REST application."""
    dist_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
    if os.path.exists(dist_folder):
        app = Flask(__name__, static_folder=dist_folder, static_url_path="")
    else:
        app = Flask(__name__)

    CORS(app)

    @app.route("/healthz", methods=["GET"])
    def health_check():
        """Health check endpoint for cloud orchestrators."""
        return jsonify({
            "status": "ready" if _INITIALIZED else "warming_up",
            "initialized": _INITIALIZED
        }), 200

    # Register blueprints
    app.register_blueprint(graph_bp)
    app.register_blueprint(entities_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(resolution_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(evolution_bp)
    app.register_blueprint(infrastructure_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(autonomous_bp)

    if os.path.exists(dist_folder):
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            if path != "" and os.path.exists(os.path.join(dist_folder, path)):
                return send_from_directory(dist_folder, path)
            return send_from_directory(dist_folder, "index.html")
    else:
        @app.route("/", methods=["GET"])
        def home():
            """Health check endpoint."""
            return "Identity Resolution Backend Running"

    return app


app = create_app()

# Warm up in background thread so Gunicorn binds to the port immediately without timing out Render
threading.Thread(target=startup, daemon=True).start()


if __name__ == "__main__":
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG)
