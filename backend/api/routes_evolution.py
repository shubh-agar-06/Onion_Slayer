"""Continuous Intelligence Intake & Evolution REST API Endpoints."""

from __future__ import annotations

import json
from flask import Blueprint, jsonify, request
from core.logging import logger
from graph.graph_engine import NetworkXGraphEngine
from graph.serializers import CytoscapeSerializer
from services.evolution_engine import EvolutionEngine

evolution_bp = Blueprint("evolution_bp", __name__)


@evolution_bp.route("/analyst/submit", methods=["POST"])
def submit_analyst_intelligence():
    """
    Primary analyst intelligence submission endpoint.
    Accepts raw actor profile & credentials, runs the complete 5-stage pipeline,
    and dynamically evolves the permanent knowledge graph.
    """
    payload = request.get_json(silent=True) or {}
    source_dataset = payload.get("source_dataset") or payload.get("source") or "Analyst Submission"
    analyst_name = payload.get("analyst_name") or payload.get("analyst_id") or "analyst_1"

    if not payload:
        return jsonify({"error": "Empty intelligence submission payload."}), 400

    result = EvolutionEngine.ingest_submission(
        payload=payload,
        source_dataset=source_dataset,
        analyst_name=analyst_name,
    )

    return jsonify(result)


@evolution_bp.route("/analyst/preview", methods=["POST"])
def preview_analyst_intelligence():
    """
    Pre-ingestion resolution preview for single actor dossier.
    Validates, normalizes, and forecasts graph linking without modifying the database.
    """
    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({"error": "Empty dossier payload."}), 400
    preview = EvolutionEngine.preview_submission(payload)
    return jsonify(preview)


@evolution_bp.route("/datasets/preview", methods=["POST"])
def preview_dataset():
    """
    Pre-ingestion resolution preview for bulk dataset import.
    Parses and forecasts linking outcomes across all records in batch.
    """
    payload = request.get_json(silent=True) or {}
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not records or not isinstance(records, list):
        return jsonify({"error": "Payload must contain a list of 'records' to preview."}), 400
    preview = EvolutionEngine.preview_dataset(records)
    return jsonify(preview)


@evolution_bp.route("/datasets/import", methods=["POST"])
def import_dataset():
    """
    Bulk dataset import endpoint (JSON array or multi-record payload).
    Executes full continuous intelligence pipeline across each record,
    updating existing identities, merging duplicates, and expanding the graph.
    """
    payload = request.get_json(silent=True) or {}
    records = payload.get("records") if isinstance(payload, dict) else payload
    source_name = payload.get("source_name", "Dataset Import") if isinstance(payload, dict) else "Dataset Import"
    analyst_name = payload.get("analyst_name", "system") if isinstance(payload, dict) else "system"

    if not records or not isinstance(records, list):
        return jsonify({"error": "Payload must contain a list of 'records' to import."}), 400

    total_new_nodes = 0
    total_updated_nodes = 0
    total_rels_created = 0
    total_rels_strengthened = 0
    total_suggestions = 0
    total_clusters_merged = 0

    for rec in records:
        try:
            res = EvolutionEngine.ingest_submission(
                payload=rec,
                source_dataset=source_name,
                analyst_name=analyst_name,
            )
            ev = res.get("evolution_report", {})
            total_new_nodes += ev.get("new_nodes_created", 0)
            total_updated_nodes += ev.get("existing_nodes_updated", 0)
            total_rels_created += ev.get("relationships_created", 0)
            total_rels_strengthened += ev.get("relationships_strengthened", 0)
            total_suggestions += ev.get("suggestions_generated", 0)
            total_clusters_merged += ev.get("clusters_merged", 0)
        except Exception as e:
            logger.error("Failed importing record %s: %s", rec, e)

    # Rebuild graph
    G = NetworkXGraphEngine.build_graph()

    return jsonify({
        "status": "DATASET_IMPORT_SUCCESS",
        "source_dataset": source_name,
        "records_processed": len(records),
        "new_nodes_created": total_new_nodes,
        "existing_nodes_updated": total_updated_nodes,
        "relationships_created": total_rels_created,
        "relationships_strengthened": total_rels_strengthened,
        "suggestions_generated": total_suggestions,
        "clusters_merged": total_clusters_merged,
        "graph_statistics": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
        },
    })


@evolution_bp.route("/identity/suggestions", methods=["GET"])
@evolution_bp.route("/api/v1/identity/suggestions", methods=["GET"])
def list_suggestions():
    """List pending identity suggestions awaiting analyst review."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    suggestions = EvolutionEngine.get_pending_suggestions(limit=limit, offset=offset)

    return jsonify({
        "suggestions": suggestions,
        "count": len(suggestions),
        "limit": limit,
        "offset": offset,
    })


@evolution_bp.route("/identity/approve", methods=["POST"])
@evolution_bp.route("/api/v1/identity/approve", methods=["POST"])
def approve_suggestion():
    """Analyst approves candidate merge suggestion -> merges clusters & creates SAME_AS edge."""
    payload = request.get_json(silent=True) or {}
    suggestion_id = payload.get("suggestion_id")
    analyst_name = payload.get("analyst_name", "analyst_1")
    notes = payload.get("notes", "")

    if not suggestion_id:
        return jsonify({"error": "'suggestion_id' is required."}), 400

    result = EvolutionEngine.approve_suggestion(
        suggestion_id=int(suggestion_id),
        analyst_name=analyst_name,
        notes=notes,
    )
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@evolution_bp.route("/identity/reject", methods=["POST"])
@evolution_bp.route("/api/v1/identity/reject", methods=["POST"])
def reject_suggestion():
    """Analyst rejects candidate merge suggestion -> keeps entities separate and logs decision."""
    payload = request.get_json(silent=True) or {}
    suggestion_id = payload.get("suggestion_id")
    analyst_name = payload.get("analyst_name", "analyst_1")
    notes = payload.get("notes", "")

    if not suggestion_id:
        return jsonify({"error": "'suggestion_id' is required."}), 400

    result = EvolutionEngine.reject_suggestion(
        suggestion_id=int(suggestion_id),
        analyst_name=analyst_name,
        notes=notes,
    )
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@evolution_bp.route("/graph/refresh", methods=["POST"])
def refresh_graph():
    """Explicitly invalidate and rebuild the NetworkX graph cache."""
    G = NetworkXGraphEngine.build_graph()
    return jsonify({
        "status": "GRAPH_REFRESHED",
        "nodes_count": G.number_of_nodes(),
        "edges_count": G.number_of_edges(),
    })


@evolution_bp.route("/identity/<int:identity_id>/provenance", methods=["GET"])
def get_identity_provenance(identity_id: int):
    """Retrieve full chronological evidence timeline and confidence evolution for an identity."""
    provenance = EvolutionEngine.get_provenance_for_target("identity", identity_id)
    return jsonify({
        "identity_id": identity_id,
        "provenance_timeline": provenance,
        "timeline_count": len(provenance),
    })


@evolution_bp.route("/vendor/<int:vendor_id>/provenance", methods=["GET"])
def get_vendor_provenance(vendor_id: int):
    """Retrieve full chronological evidence timeline and confidence evolution for a vendor."""
    provenance = EvolutionEngine.get_provenance_for_target("vendor", vendor_id)
    return jsonify({
        "vendor_id": vendor_id,
        "provenance_timeline": provenance,
        "timeline_count": len(provenance),
    })
