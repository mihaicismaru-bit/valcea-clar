# Rulare nativă pe Windows — MCLENOVO

Decizia proprietarului din 23 octombrie 2026 înlocuiește NAS-ul cu Windows. Acest pachet instalează colectarea și backupul local. Contractele agenților există, dar analiza cu modele, social media și publicarea nu sunt conectate.

## Instalare

Din copia de lucru, deschide `deploy/windows/ramnicu/Install.cmd`. Folosește Python 3.12+ deja instalat, creează un mediu local cu acces la bibliotecile existente și înregistrează `ValceaClar-Ramnicu-Daily`. Nu solicită parole. Instalatorul folosește Python și schtasks.exe; nu execută scripturi PowerShell și nu schimbă politica lor de execuție.

Colectarea pornește zilnic la **07:15 în fusul orar al calculatorului**, cu recuperare după o pornire ratată, protecție contra suprapunerilor și limită de o oră. Utilizatorul Windows trebuie să rămână conectat; ecranul poate fi blocat. Oprirea, deconectarea utilizatorului și suspendarea calculatorului împiedică rularea la oră; acest instalator nu modifică setările de energie.

Instalatorul declanșează o primă execuție. Verifică rezultatul cu `Status.cmd`: existența taskului nu dovedește o colectare reușită. Codul 2 înseamnă colectare degradată; 0 înseamnă că parcurgerea delimitată s-a terminat, fără a certifica acoperirea editorială completă.

## Date și diagnostic

- `runtime/ramnicu/`: SQLite, originale cu SHA-256, texte, legături și coadă de analiză.
- `runtime/windows/status.json`: rezultatul ultimei execuții; devine STALE după 30 ore.
- `runtime/windows/scheduler.json`: dovada instalării sau eroarea exactă; verificarea live a taskului rămâne în Status.cmd.
- `runtime/windows/logs/`: rezultate și erori.
- `runtime/backups/`: ultimele șapte arhive, cu snapshot SQLite consistent și manifest verificat integral.

Backupul este pe același calculator. Copia externă în cPanel nu este configurată.

Extragerea PDF folosește pdftotext când există, apoi pypdf din Python. Procesul are limită de 45 secunde. PDF-urile scanate rămân NEEDS_OCR; OCR nu este instalat.

## Comenzi din rădăcina copiei

```powershell
python -m administratie.ramnicu_valcea.windows_runtime run
python -m administratie.ramnicu_valcea.windows_runtime status
python -m administratie.ramnicu_valcea.windows_runtime backup
python -m administratie.ramnicu_valcea.windows_runtime restore --archive runtime/backups/ARHIVA.zip --target runtime/restore-verificat
```

Restaurarea cere un director nou, verifică hashurile înainte de scriere și apoi integritatea bazei și a originalelor. Nu suprascrie datele active.

Oprirea programării:

```powershell
Disable-ScheduledTask -TaskName ValceaClar-Ramnicu-Daily
```

Respectăm robots.txt și domeniile oficiale configurate. Restricția oficială /documente/ observată pe 16 octombrie rămâne un blocaj pentru anexe până la verificarea unei căi oficiale permise sau obținerea permisiunii. Mutarea pe Windows nu rezolvă această restricție.
