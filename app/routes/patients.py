from flask import Blueprint, redirect, url_for

patients_bp = Blueprint("patients", __name__)


@patients_bp.route("/")
def list_patients():
    return redirect(url_for("parties.list_parties"))


@patients_bp.route("/<int:patient_id>")
def detail_patient(patient_id):
    return redirect(url_for("parties.detail_party", party_id=patient_id))
