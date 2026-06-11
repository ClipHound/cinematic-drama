# Start Django backend server
# Run this script from the repository root

Set-Location -LiteralPath (Join-Path $PSScriptRoot "django-backend")
python manage.py runserver 127.0.0.1:8787
