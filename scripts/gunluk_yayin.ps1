# GÜNLÜK YAYIN — zamanlanmış görev sarmalayıcısı
#
# Görev Zamanlayıcı bunu çağırır; başka hiçbir şey çağırmaz.
#
# NEDEN SARMALAYICI. Zamanlanmış bir görevin çıktısı kimse bakmadığı sürece
# görünmez. Bu sarmalayıcı üç şey yapar:
#
#   1. çalışma dizinini ve ortamı sabitler (görev zamanlayıcı farklı bir
#      dizinden başlatır ve sanal ortam etkin değildir)
#   2. çıktıyı TARİHLİ bir günlüğe yazar -- sessiz başarısızlık kalmasın
#   3. çıkış kodunu koruyarak döner; görev zamanlayıcı başarısızlığı görsün
#
# KORUMALAR HATTIN İÇİNDEDİR (src/operational/pipeline.py): kirli ağaç,
# katalog tazeliği, katalog monotonluğu, şema, dil, hücre bandı. Hepsi
# yayımı DURDURUR; bu sarmalayıcı onları atlamaz.

# ErrorActionPreference "Stop" DEĞİL "Continue".
#
# PowerShell 5.1'de yerel bir programın stderr çıktısı, boru hattında
# ErrorRecord'a çevrilir; "Stop" altında bu, betiği ANINDA sonlandırır ve
# günlüğe HİÇBİR ŞEY yazılmaz. Ölçüldü: ilk sürümde günlükte yalnızca başlık
# satırı vardı, çıkış kodu 1 idi ve sebep görünmüyordu (V41).
#
# Hattın kendi korumaları zaten yayımı durduruyor; sarmalayıcının işi
# durdurmak değil, OLAN BİTENİ KAYDETMEKTİR.
$ErrorActionPreference = "Continue"
$Kok = Split-Path -Parent $PSScriptRoot
Set-Location $Kok

$GunlukDizin = Join-Path $Kok "data\publish\_gunluk"
New-Item -ItemType Directory -Force -Path $GunlukDizin | Out-Null
$Gunluk = Join-Path $GunlukDizin ("yayin_" + (Get-Date -Format "yyyy-MM-dd_HHmm") + ".log")

$Python = Join-Path $Kok ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    "python bulunamadi: $Python" | Out-File -FilePath $Gunluk -Encoding utf8
    exit 1
}

"=== gunluk yayin basladi: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Out-File -FilePath $Gunluk -Encoding utf8

# 2>&1 yerine cmd düzeyinde yönlendirme: PowerShell'in ErrorRecord
# sarmalamasına hiç girmez, ham metin olarak günlüğe yazılır.
$Gecici = [System.IO.Path]::GetTempFileName()
$psi = Start-Process -FilePath $Python `
    -ArgumentList "-u", "-m", "src.operational.pipeline" `
    -WorkingDirectory $Kok -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput $Gecici -RedirectStandardError "$Gecici.err"
$Kod = $psi.ExitCode
Get-Content $Gecici -ErrorAction SilentlyContinue |
    Out-File -FilePath $Gunluk -Encoding utf8 -Append
Get-Content "$Gecici.err" -ErrorAction SilentlyContinue |
    Out-File -FilePath $Gunluk -Encoding utf8 -Append
Remove-Item $Gecici, "$Gecici.err" -Force -ErrorAction SilentlyContinue

"=== bitti: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') · cikis kodu $Kod ===" |
    Out-File -FilePath $Gunluk -Encoding utf8 -Append

# 30 gunden eski gunlukleri temizle -- disk dolmasin, iz de kaybolmasin
Get-ChildItem $GunlukDizin -Filter "yayin_*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force

exit $Kod
