from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
import io

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
        "periodontic": "Periodontoloji (Diş Eti)",
        "endodontic": "Endodonti (Kanal)",
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
        "periodontic": "Periodontoloji (Diş Eti)",
        "endodontic": "Endodonti (Kanal)",
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
        "periodontic": "Periodontoloji (Diş Eti)",
        "endodontic": "Endodonti (Kanal)",
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


CATEGORY_MAP = {
    "ortodonti": "orthodontic",
    "orthodontic": "orthodontic",
    "protetik": "prosthetic",
    "prosthetic": "prosthetic",
    "cerrahi": "surgical",
    "surgical": "surgical",
    "koruyucu": "preventive",
    "preventive": "preventive",
    "restoratif": "restorative",
    "restorative": "restorative",
    "periodontik": "periodontic",
    "periodontoloji": "periodontic",
    "periodontic": "periodontic",
    "endodontik": "endodontic",
    "endodonti": "endodontic",
    "endodontic": "endodontic",
    "implant": "implant",
    "kozmetik": "cosmetic",
    "cosmetic": "cosmetic",
    "diger": "other",
    "other": "other",
}

CATEGORY_LABELS_REV = {
    "ortodonti": "orthodontic",
    "protetik": "prosthetic",
    "cerrahi": "surgical",
    "koruyucu": "preventive",
    "restoratif": "restorative",
    "periodontoloji": "periodontic",
    "periodontik": "periodontic",
    "perio": "periodontic",
    "endodonti": "endodontic",
    "endodontik": "endodontic",
    "endo": "endodontic",
    "implant": "implant",
    "kozmetik": "cosmetic",
    "diğer": "other",
    "diger": "other",
}


@treatments_bp.route("/import", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def import_treatments():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("Dosya seçilmedi.", "danger")
            return redirect(url_for("treatments.import_treatments"))

        filename = file.filename.lower()
        if not (filename.endswith(".xlsx") or filename.endswith(".xls")):
            flash("Yalnızca .xlsx veya .xls dosyaları desteklenir.", "danger")
            return redirect(url_for("treatments.import_treatments"))

        try:
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(file.read()), read_only=True, data_only=True)
            ws = wb.active

            rows = list(ws.iter_rows(min_row=2, values_only=True))
            added = 0
            updated = 0
            skipped = 0

            for row in rows:
                if not row or not row[0]:
                    skipped += 1
                    continue

                name = str(row[0]).strip()
                if not name:
                    skipped += 1
                    continue

                # Column B: category (TR or EN)
                raw_cat = str(row[1]).strip().lower() if len(row) > 1 and row[1] else "other"
                category = CATEGORY_MAP.get(raw_cat, "other")

                # Column C: price EUR
                try:
                    price = float(row[2]) if len(row) > 2 and row[2] else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                # Column D: description
                description = str(row[3]).strip() if len(row) > 3 and row[3] else None

                existing = db.session.execute(
                    db.select(Treatment).where(Treatment.name == name)
                ).scalar_one_or_none()

                if existing:
                    existing.price_eur = price
                    existing.category = category
                    if description:
                        existing.description = description
                    updated += 1
                else:
                    db.session.add(Treatment(
                        name=name,
                        category=category,
                        price_eur=price,
                        description=description,
                        is_active=True,
                    ))
                    added += 1

            db.session.commit()
            wb.close()

            parts = []
            if added:
                parts.append(f"{added} yeni")
            if updated:
                parts.append(f"{updated} güncellendi")
            if skipped:
                parts.append(f"{skipped} atlandı")

            flash(f"İçe aktarma tamamlandı: {', '.join(parts) if parts else 'Değişiklik yok'}.", "success")
        except Exception as e:
            flash(f"İçe aktarma hatası: {str(e)}", "danger")

        return redirect(url_for("treatments.list_treatments"))

    return render_template("treatments/import.html")


@treatments_bp.route("/api/update", methods=["POST"])
@login_required
@roles_required("admin")
def api_update_treatment():
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"error": "Geçersiz istek"}), 400

    treatment = db.session.get(Treatment, data["id"])
    if not treatment:
        return jsonify({"error": "Tedavi bulunamadı"}), 404

    if "name" in data:
        treatment.name = str(data["name"]).strip()
    if "category" in data:
        cat_raw = str(data["category"]).strip().lower()
        treatment.category = CATEGORY_MAP.get(cat_raw, cat_raw)
    if "price_eur" in data:
        try:
            treatment.price_eur = float(data["price_eur"])
        except (ValueError, TypeError):
            return jsonify({"error": "Geçersiz fiyat"}), 400
    if "description" in data:
        treatment.description = str(data["description"]).strip() or None

    db.session.commit()

    return jsonify({
        "ok": True,
        "treatment": {
            "id": treatment.id,
            "name": treatment.name,
            "category": treatment.category,
            "price_eur": treatment.price_eur,
            "description": treatment.description or "",
        }
    })
