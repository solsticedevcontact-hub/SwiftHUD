# Signs dist\SwiftHUD.exe with a self-signed certificate named SoslticeDeveloper.
# NOTE: self-signed = Windows SmartScreen will still warn until you use a trusted CA certificate.
$exe  = Join-Path $PSScriptRoot "dist\SwiftHUD.exe"
if (-not (Test-Path $exe)) { Write-Host "Build the EXE first (build_exe.bat)"; exit 1 }

$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -eq "CN=SoslticeDeveloper" } | Select-Object -First 1
if (-not $cert) {
  $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=SoslticeDeveloper" `
          -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(5)
  Export-Certificate -Cert $cert -FilePath (Join-Path $PSScriptRoot "SoslticeDeveloper.cer") | Out-Null
}
Set-AuthenticodeSignature -FilePath $exe -Certificate $cert -HashAlgorithm SHA256 `
  -TimestampServer "http://timestamp.digicert.com" | Format-List
Write-Host "Signed. (Share SoslticeDeveloper.cer only if you want others to trust it manually)"
