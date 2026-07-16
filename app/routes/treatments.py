from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app.extensions import db
from app.models.models import Treatment, TreatmentCategory
from app.authz import roles_required

treatments_bp = Blueprint("treatments", __name__)


@treatments_bp.route("/")
@login_required
def list_treatments():
    category = request.args.get("category", "")
    search = request.args.get("search", "").strip()

    query = db.select(Treatment).where(Treatment.is_active == True)

    if category:
        query = query.where(Treatment.category == category)
    if search:
        query = query.where(Treatment.name.ilike(f"%{search}%"))

    query = query.order_by(Treatment.category, Treatment.name)
    treatments = db.session.execute(query).scalars().all()

    categories = TreatmentCategory.ALL
    category_labels = {
        "orthodontic": "Ortodonti",
        "prosthetic": "Protetik",
        "surgical": "Cerrahi",
        "preventive": "Koruyucu",
        "restorative": "Restoratif",
        "periodontic": "Perio/Endo",
        "implant": "İmplant",
        "cosmetic": "Kozmetik",
        "other": "Diğer",
    }

    return render_template(
        "treatments/list.html",
        treatments=treatments,
        categories=categories,
        category_labels=category_labels,
        selected_category=category,
        search=search,
    )


@treatments_bp.route("/add", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def add_treatment():
    if request.method == "POST":
        treatment = Treatment(
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip() or None,
            category=request.form["category"],
            price_eur=float(request.form["price_eur"]),
        )
        db.session.add(treatment)
        db.session.commit()
        flash(f"{treatment.name} eklendi.", "success")
        return redirect(url_for("treatments.list_treatments"))

    category_labels = {
        "orthodontic": "Ortodonti",
        "prosthetic": "Protetik",
        "surgical": "Cerrahi",
        "preventive": "Koruyucu",
        "restorative": "Restoratif",
        "periodontic": "Perio/Endo",
        "implant": "İmplant",
        "cosmetic": "Kozmetik",
        "other": "Diğer",
    }
    return render_template("treatments/form.html", treatment=None, category_labels=category_labels)


@treatments_bp.route("/<int:treatment_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_treatment(treatment_id):
    treatment = db.get_or_404(Treatment, treatment_id)

    if request.method == "POST":
        treatment.name = request.form["name"].strip()
        treatment.description = request.form.get("description", "").strip() or None
        treatment.category = request.form["category"]
        treatment.price_eur = float(request.form["price_eur"])
        db.session.commit()
        flash(f"{treatment.name} güncellendi.", "success")
        return redirect(url_for("treatments.list_treatments"))

    category_labels = {
        "orthodontic": "Ortodonti",
        "prosthetic": "Protetik",
        "surgical": "Cerrahi",
        "preventive": "Koruyucu",
        "restorative": "Restoratif",
        "periodontic": "Perio/Endo",
        "implant": "İmplant",
        "cosmetic": "Kozmetik",
        "other": "Diğer",
    }
    return render_template("treatments/form.html", treatment=treatment, category_labels=category_labels)


@treatments_bp.route("/<int:treatment_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_treatment(treatment_id):
    treatment = db.get_or_404(Treatment, treatment_id)
    treatment.is_active = False
    db.session.commit()
    flash(f"{treatment.name} silindi.", "warning")
    return redirect(url_for("treatments.list_treatments"))
