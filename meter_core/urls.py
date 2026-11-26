from django.urls import path
from . import views

urlpatterns = [
    path("", views.role_root_redirect, name="role_root_redirect"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/resident/", views.resident_dashboard, name="resident_dashboard"),
    path("bills/<int:bill_id>/edit/", views.edit_bill_view, name="edit_bill"),
    path("bills/<int:bill_id>/approve/", views.approve_bill_view, name="approve_bill"),
    path("export/statement.xlsx/", views.export_statement_xlsx, name="export_statement_xlsx"),
    path("bills/<int:bill_id>/ai-analyze/", views.analyze_bill_ai_view, name="analyze_bill_ai"),
]