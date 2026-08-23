# Шаблоны результата диагностики

| Файл | Назначение |
|------|------------|
| [diagnosis-stazh-report.md](diagnosis-stazh-report.md) | Пустой шаблон для заполнения |
| [diagnosis-stazh-report.example.md](diagnosis-stazh-report.example.md) | Пример без реальных ПДн |
| `out/` | Локальная сборка HTML/PDF (в `.gitignore`) |

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/build_diagnosis_report_pdf.py scripts/assets/templates/diagnosis-stazh-report.example.md
```

Канон: [playbook-diagnosis-result-standard.md](../../../docs/marketing-sales/playbook-diagnosis-result-standard.md).
