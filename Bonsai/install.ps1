if (!(Test-Path "./Bonsai.exe")) {
    Invoke-WebRequest "https://github.com/bonsai-rx/bonsai/releases/download/2.6.3/Bonsai.zip" -OutFile "temp.zip"
    Expand-Archive "temp.zip" -DestinationPath "." -Force
    Remove-Item -Path "temp.zip"
}
& .\Bonsai.exe --no-editor