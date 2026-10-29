"""Run step-1 schema migration + group→folder migration (same as app startup)."""
from app import app, ensure_schema, migrate_groups_to_folders, seed_if_needed, Folder, File

with app.app_context():
    ensure_schema()
    migrate_groups_to_folders()
    seed_if_needed()
    fc = Folder.query.count()
    files_with_folder = File.query.filter(File.folder_id.isnot(None)).count()
    print(f"folders={fc}, files_with_folder_id={files_with_folder}")
