# sauvegarde.ps1 - sauvegarde la base PostgreSQL et les images dans le dossier "backups"
# A placer a la racine du projet (C:\marche_tn). Conserve les 10 dernieres sauvegardes.
#
# Lancer a la main :
#   powershell -ExecutionPolicy Bypass -File .\sauvegarde.ps1

$ErrorActionPreference = 'Stop'

$racine  = Split-Path -Parent $MyInvocation.MyCommand.Path
$dossier = Join-Path $racine 'backups'
$pgBin   = Join-Path $env:USERPROFILE 'Documents\pgsql\bin'
$pgData  = Join-Path $env:USERPROFILE 'Documents\pgsql\data'
$garder  = 10

New-Item -ItemType Directory -Force -Path $dossier | Out-Null

# --- Lecture des acces dans le fichier .env (le mot de passe n'est jamais affiche) ---
$cfg = @{ DB_NAME = 'marche_tn'; DB_USER = 'postgres'; DB_PASSWORD = ''; DB_HOST = 'localhost'; DB_PORT = '5432' }
$fichierEnv = Join-Path $racine '.env'
if (Test-Path $fichierEnv) {
    foreach ($ligne in Get-Content $fichierEnv) {
        if ($ligne -match '^\s*(DB_[A-Z]+)\s*=\s*(.*?)\s*$') {
            $cfg[$matches[1]] = $matches[2].Trim('"').Trim("'")
        }
    }
}
$dbNom  = $cfg['DB_NAME']
$dbUser = $cfg['DB_USER']
$dbHote = $cfg['DB_HOST']
$dbPort = $cfg['DB_PORT']
$env:PGPASSWORD = $cfg['DB_PASSWORD']

try {
    # --- PostgreSQL doit tourner : on le demarre s'il est arrete ---
    & "$pgBin\pg_isready.exe" -h $dbHote -p $dbPort | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'PostgreSQL est arrete : demarrage...'
        & "$pgBin\pg_ctl.exe" -D $pgData -l (Join-Path $dossier 'postgres.log') -w start | Out-Null
        & "$pgBin\pg_isready.exe" -h $dbHote -p $dbPort | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Impossible de joindre PostgreSQL. Aucune sauvegarde creee.'
        }
    }

    $horodatage = Get-Date -Format 'yyyyMMdd_HHmm'

    # --- 1. Sauvegarde de la base (ecrite d'abord en .partial pour ne jamais laisser un fichier vide) ---
    $dump    = Join-Path $dossier "marche_tn_$horodatage.dump"
    $partiel = "$dump.partial"
    & "$pgBin\pg_dump.exe" -h $dbHote -p $dbPort -U $dbUser -F c -f $partiel $dbNom
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $partiel) -or (Get-Item $partiel).Length -eq 0) {
        if (Test-Path $partiel) { Remove-Item $partiel -Force }
        throw 'Echec de pg_dump : aucune sauvegarde de la base creee.'
    }
    Move-Item $partiel $dump
    Write-Host "Base sauvegardee : $dump"

    # --- 2. Sauvegarde des images ---
    $media = Join-Path $racine 'media'
    if (Test-Path $media) {
        $zip = Join-Path $dossier "media_$horodatage.zip"
        Compress-Archive -Path $media -DestinationPath $zip -Force
        Write-Host "Images sauvegardees : $zip"
    }

    # --- 3. On ne garde que les $garder dernieres sauvegardes de chaque type ---
    foreach ($motif in @('marche_tn_*.dump', 'media_*.zip')) {
        Get-ChildItem -Path $dossier -Filter $motif |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip $garder |
            Remove-Item -Force
    }

    Write-Host 'Sauvegarde terminee.'
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
