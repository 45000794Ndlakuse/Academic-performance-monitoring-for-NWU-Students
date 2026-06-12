"""
PSR Web Application - Flask Backend
Academic Performance Status Reports based on Van der Merwe et al. (2018)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from algorithms import (
    algorithm1_linear_pmark, rank_students,
    algorithm2_participation_plan, algorithm3_weight_selection,
    compute_dea_classes
)
from database import (
    init_db, get_module, get_all_modules, get_students_for_module,
    get_student_detail, save_psr_result, add_module, add_student,
    update_student_scores
)

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

# ──────────────────────────────────────────────
# Serve frontend
# ──────────────────────────────────────────────
#@app.route("/")
#def home():
#    return "Welcome to your PSR app"
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ──────────────────────────────────────────────
# Modules
# ──────────────────────────────────────────────
@app.route("/api/modules", methods=["GET"])
def list_modules():
    return jsonify(get_all_modules())


@app.route("/api/modules", methods=["POST"])
def create_module():
    data = request.json
    mid = add_module(
        name=data["name"],
        factor_names=data["factor_names"],
        total_assessments=data["total_assessments"],
        weight_lower=data.get("weight_lower", 0.01),
        weight_upper=data.get("weight_upper", 0.40)
    )
    return jsonify({"id": mid, "message": "Module created"}), 201


@app.route("/api/modules/<int:module_id>", methods=["GET"])
def get_module_detail(module_id):
    m = get_module(module_id)
    if not m:
        return jsonify({"error": "Module not found"}), 404
    return jsonify(m)


# ──────────────────────────────────────────────
# Students
# ──────────────────────────────────────────────
@app.route("/api/modules/<int:module_id>/students", methods=["GET"])
def list_students(module_id):
    students = get_students_for_module(module_id)
    return jsonify(students)


@app.route("/api/modules/<int:module_id>/students", methods=["POST"])
def create_student(module_id):
    data = request.json
    sid = add_student(
        module_id=module_id,
        student_number=data["student_number"],
        name=data["name"],
        factor_averages=data["factor_averages"]
    )
    return jsonify({"id": sid, "message": "Student added"}), 201


@app.route("/api/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    s = get_student_detail(student_id)
    if not s:
        return jsonify({"error": "Student not found"}), 404
    return jsonify(s)


@app.route("/api/students/<int:student_id>/scores", methods=["PUT"])
def update_scores(student_id):
    data = request.json
    s = get_student_detail(student_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    update_student_scores(student_id, s["module_id"], data["factor_averages"])
    return jsonify({"message": "Scores updated"})


# ──────────────────────────────────────────────
# PSR - Full module analysis
# ──────────────────────────────────────────────
@app.route("/api/modules/<int:module_id>/psr", methods=["GET"])
def compute_module_psr(module_id):
    """
    Runs Algorithm 1 + DEA for all students in a module.
    Returns ranked list with p-marks and class rankings.
    """
    module = get_module(module_id)
    if not module:
        return jsonify({"error": "Module not found"}), 404

    students = get_students_for_module(module_id)
    if not students:
        return jsonify({"error": "No students in module"}), 400

    # Filter students with complete factor data
    valid_students = [s for s in students if len(s["factor_averages"]) > 0]

    # Algorithm 1: rank all students
    ranked = rank_students(valid_students)

    # DEA class ranking
    dea_ranked = compute_dea_classes(ranked)
    dea_map = {s["id"]: s["dea_class"] for s in dea_ranked}

    # Merge DEA classes into ranked list
    for s in ranked:
        s["dea_class"] = dea_map.get(s["id"], 0)
        save_psr_result(s["id"], module_id, s)

    # Class statistics
    avg_pmarks = [s["avg_pmark"] for s in ranked]
    pass_rate = sum(1 for p in avg_pmarks if p >= 50) / len(avg_pmarks) * 100
    distinction_rate = sum(1 for p in avg_pmarks if p >= 75) / len(avg_pmarks) * 100
    at_risk = sum(1 for p in avg_pmarks if p < 50)

    return jsonify({
        "module": module,
        "students": ranked,
        "statistics": {
            "class_average": round(sum(avg_pmarks) / len(avg_pmarks), 2),
            "pass_rate": round(pass_rate, 1),
            "distinction_rate": round(distinction_rate, 1),
            "at_risk_count": at_risk,
            "total_students": len(ranked)
        }
    })


# ──────────────────────────────────────────────
# Individual student PSR
# ──────────────────────────────────────────────
@app.route("/api/students/<int:student_id>/psr", methods=["GET"])
def student_psr(student_id):
    """Full PSR for a single student including improvement plan."""
    s = get_student_detail(student_id)
    if not s:
        return jsonify({"error": "Not found"}), 404

    module = get_module(s["module_id"])
    if not module:
        return jsonify({"error": "Module not found"}), 404

    # Algorithm 1
    psr = algorithm1_linear_pmark(
        s["factor_averages"],
        weights_bounds=(module["weight_lower"], module["weight_upper"])
    )

    # Rank among peers
    all_students = get_students_for_module(s["module_id"])
    ranked = rank_students(all_students)
    dea = compute_dea_classes(ranked)
    my_rank = next((r["rank"] for r in ranked if r["id"] == student_id), None)
    my_dea = next((r["dea_class"] for r in dea if r["id"] == student_id), None)

    # Determine performance tier
    avg = psr["avg_pmark"]
    if avg >= 75:
        tier = "distinction"
    elif avg >= 60:
        tier = "good"
    elif avg >= 50:
        tier = "satisfactory"
    elif avg >= 40:
        tier = "at_risk"
    else:
        tier = "critical"

    return jsonify({
        "student": s,
        "module": module,
        "psr": {**psr, "rank": my_rank, "dea_class": my_dea, "tier": tier},
        "total_students": len(all_students)
    })


# ──────────────────────────────────────────────
# Algorithm 2 - Improvement plan
# ──────────────────────────────────────────────
@app.route("/api/students/<int:student_id>/improvement", methods=["POST"])
def improvement_plan(student_id):
    """
    Algorithm 2: Generate participation improvement plan.
    Body: { remaining_assessments: [], delta: 5.0 }
    """
    s = get_student_detail(student_id)
    if not s:
        return jsonify({"error": "Not found"}), 404

    module = get_module(s["module_id"])
    data = request.json

    remaining = data.get("remaining_assessments", [1] * len(s["factor_averages"]))
    delta = float(data.get("delta", 5.0))

    # Get weights from Algorithm 1
    psr = algorithm1_linear_pmark(
        s["factor_averages"],
        weights_bounds=(module["weight_lower"], module["weight_upper"])
    )

    plan = algorithm2_participation_plan(
        factor_averages=s["factor_averages"],
        remaining_assessments=remaining,
        total_assessments=module["total_assessments"],
        delta=delta,
        weights_min=psr["weights_min"]
    )

    return jsonify({
        "student": s,
        "module": module,
        "current_psr": psr,
        "improvement_plan": plan
    })


# ──────────────────────────────────────────────
# Algorithm 3 - Weight selection for lecturer
# ──────────────────────────────────────────────
@app.route("/api/modules/<int:module_id>/weight-selection", methods=["POST"])
def weight_selection(module_id):
    """
    Algorithm 3: Find weights to achieve a target class average.
    Body: { target_average: 70.0 }
    """
    module = get_module(module_id)
    if not module:
        return jsonify({"error": "Module not found"}), 404

    students = get_students_for_module(module_id)
    if not students:
        return jsonify({"error": "No students"}), 400

    data = request.json
    target = float(data.get("target_average", 65.0))

    all_averages = [s["factor_averages"] for s in students
                    if len(s["factor_averages"]) == len(module["factor_names"])]

    result = algorithm3_weight_selection(
        all_factor_averages=all_averages,
        target_class_average=target,
        weights_bounds=(module["weight_lower"], module["weight_upper"])
    )

    return jsonify({
        "module": module,
        "weight_selection": result
    })


if __name__ == "__main__":
    init_db()
    print("✓ Database initialised")
    print("✓ PSR Application running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
