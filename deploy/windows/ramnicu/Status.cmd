@echo off
pushd "%~dp0..\..\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m administratie.ramnicu_valcea.windows_runtime status
) else (
    python -m administratie.ramnicu_valcea.windows_runtime status
)
schtasks.exe /Query /TN "ValceaClar-Ramnicu-Daily" /V /FO LIST
popd
pause
