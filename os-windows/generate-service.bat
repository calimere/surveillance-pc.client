REM activer l'environnement virtuel si nécessaire
call venv\Scripts\activate

@REM # Générez un exécutable pour service_wrapper.py :
@REM # pyinstaller --onefile --hidden-import=win32timezone --name "ServiceInstaller" service_wrapper.py
@REM # Cela génère un exécutable surveillance_pc_service.exe dans le dossier dist.

.\venv\Scripts\pyinstaller.exe --onedir --noconsole --clean --hidden-import=win32timezone --name "surveillance_pc_service" --distpath ./os-windows/dist ./os-windows/service_wrapper.py

@REM Copier le fichier de configuration dans le dossier dist
COPY .\config.ini .\os-windows\dist\surveillance_pc_service\config.ini