@REM pip install pyinstaller

call venv\Scripts\activate

@REM Générez un exécutable pour run.py :
@REM --onefile : Crée un exécutable unique.
@REM --hidden-import=win32timezone : Nécessaire pour les services Windows.
@REM --name "surveillance_pc" : Donne un nom à l'exécutable.
@REM Une fois terminé, l'exécutable sera généré dans le dossier dist sous le nom surveillance_pc.exe.
@REM %USERPROFILE%\AppData\Roaming\Python\Python312\Scripts\pyinstaller --onedir --noconsole --clean --hidden-import=win32timezone --name "surveillance_pc" ../run.py
.\venv\Scripts\pyinstaller.exe --onedir --noconsole --clean --hidden-import=win32timezone --name "surveillance_pc" --distpath ./os-windows/dist ./run.py

@REM Copier le fichier de configuration dans le dossier dist
COPY .\config.ini .\os-windows\dist\surveillance_pc\config.ini