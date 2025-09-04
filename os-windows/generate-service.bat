@REM # Générez un exécutable pour service_wrapper.py :
@REM # pyinstaller --onefile --hidden-import=win32timezone --name "ServiceInstaller" service_wrapper.py
@REM # Cela génère un exécutable surveillance_pc_service.exe dans le dossier dist.

%USERPROFILE%\AppData\Roaming\Python\Python312\Scripts\pyinstaller --onefile --hidden-import=win32timezone --name "surveillance_pc_service" service_wrapper.py