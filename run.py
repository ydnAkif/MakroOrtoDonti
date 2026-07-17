from app import create_app, db
from app.models.models import User
import os

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, User=User)

if __name__ == "__main__":
    with app.app_context():
        from app.models.database import init_db, get_session, migrate_patients_to_parties, link_invoices_to_parties
        init_db()
        session = get_session()
        migrated = migrate_patients_to_parties(session)
        linked = link_invoices_to_parties(session)
        session.close()
        if migrated:
            print(f"Migrated {migrated} patients to Party records")
        if linked:
            print(f"Linked {linked} invoices to Party records")

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="127.0.0.1", port=5000)
