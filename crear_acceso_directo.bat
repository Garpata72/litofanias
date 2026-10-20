@echo off
rem Crea el acceso directo "Litofanias" en el escritorio y en el menu Inicio.
setlocal
cd /d "%~dp0"
set "DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = $env:DIR; $sh = New-Object -ComObject WScript.Shell;" ^
  "foreach ($dest in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {" ^
  "  $l = $sh.CreateShortcut((Join-Path $dest 'Litofanias.lnk'));" ^
  "  $l.TargetPath = Join-Path $d 'iniciar.bat'; $l.WorkingDirectory = $d;" ^
  "  $l.IconLocation = (Join-Path $d 'app\static\icono.ico'); $l.WindowStyle = 7;" ^
  "  $l.Description = 'Litofanias: crea litofanias a partir de tus fotos'; $l.Save() }"
if errorlevel 1 (
  echo No se ha podido crear el acceso directo.
  pause
  exit /b 1
)
echo Acceso directo "Litofanias" creado en el escritorio y en el menu Inicio.
pause
