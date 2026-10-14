param([ValidateSet('install','start','stop','status')][string]$Action='status')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$binaryRoot=Join-Path $projectRoot 'runtime\services'
# PostgreSQL for Windows cannot initialize a UTF-8 cluster below this project's
# Chinese path. Keep durable service data in a stable ASCII-only local path.
$serviceRoot='C:\RiskAgentData'
$sourcePgRoot=Join-Path $binaryRoot 'postgresql\pgsql'
$pgRoot=Join-Path $serviceRoot 'postgresql\pgsql'
$pgData=Join-Path $serviceRoot 'postgres-data'
$pgBin=Join-Path $pgRoot 'bin'
$sourceWeedExe=Join-Path $binaryRoot 'seaweedfs\weed.exe'
$weedExe=Join-Path $serviceRoot 'seaweedfs\weed.exe'
$weedData=Join-Path $serviceRoot 'seaweed-data'
$credentialFile=Join-Path $serviceRoot 'credentials.env'
$s3Config=Join-Path $serviceRoot 's3.json'
$weedPid=Join-Path $serviceRoot 'seaweed.pid'
$pgPort=55432
$s3Port=8333

function Read-Credentials {
    $values=@{}
    foreach($line in [IO.File]::ReadAllLines($credentialFile)){
        if($line -match '^([^#=]+)=(.*)$'){$values[$matches[1]]=$matches[2]}
    }
    return $values
}
function Set-EnvValue([string]$Name,[string]$Value){
    $path=Join-Path $projectRoot '.env'
    $lines=[Collections.Generic.List[string]]::new()
    if(Test-Path -LiteralPath $path){$lines.AddRange([string[]][IO.File]::ReadAllLines($path))}
    $found=$false
    for($i=0;$i -lt $lines.Count;$i++){
        if($lines[$i] -match ('^'+[regex]::Escape($Name)+'=')){$lines[$i]="$Name=$Value";$found=$true;break}
    }
    if(-not $found){$lines.Add("$Name=$Value")}
    [IO.File]::WriteAllLines($path,$lines,[Text.UTF8Encoding]::new($false))
}
function Start-Stores {
    if(-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))){throw 'PostgreSQL has not been initialized.'}
    & (Join-Path $pgBin 'pg_ctl.exe') status -D $pgData 2>$null | Out-Null
    if($LASTEXITCODE -ne 0){
        & (Join-Path $pgBin 'pg_ctl.exe') start -D $pgData -l (Join-Path $serviceRoot 'postgres.log') -w
        if($LASTEXITCODE -ne 0){throw 'PostgreSQL failed to start.'}
    }
    $weed=$null
    if(Test-Path -LiteralPath $weedPid){
        $idValue=[IO.File]::ReadAllText($weedPid).Trim()
        if($idValue -match '^\d+$'){$weed=Get-CimInstance Win32_Process -Filter "ProcessId=$idValue" -ErrorAction SilentlyContinue}
        if($weed -and ($weed.CommandLine -notlike '*weed.exe*server*' -or -not $weed.CommandLine.Contains($serviceRoot))){throw 'SeaweedFS process identity mismatch.'}
    }
    if(-not $weed){
        $weed=Start-Process -FilePath $weedExe -ArgumentList @('server',"-dir=$weedData",'-ip=127.0.0.1','-ip.bind=127.0.0.1','-master.port=9333','-volume.port=8080','-filer','-filer.port=8888','-s3',"-s3.port=$s3Port",'-s3.ip.bind=127.0.0.1',"-s3.config=$s3Config",'-s3.autoCreateBucket=true') -WorkingDirectory $serviceRoot -WindowStyle Hidden -PassThru
        [IO.File]::WriteAllText($weedPid,[string]$weed.Id)
    }
    for($attempt=0;$attempt -lt 40;$attempt++){
        try{Invoke-WebRequest "http://127.0.0.1:$s3Port" -TimeoutSec 1 -UseBasicParsing | Out-Null;break}catch{if($_.Exception.Response){break}}
        Start-Sleep -Milliseconds 250
    }
    # The S3 listener can answer before the filer finishes loading bucket metadata.
    Start-Sleep -Milliseconds 1200
}

if($Action -eq 'install'){
    if(-not (Test-Path -LiteralPath (Join-Path $sourcePgRoot 'bin\initdb.exe')) -or -not (Test-Path -LiteralPath $sourceWeedExe)){
        $localPython=Join-Path $projectRoot '.venv\Scripts\python.exe'
        if(-not (Test-Path -LiteralPath $localPython)){$localPython=(Get-Command python -ErrorAction Stop).Source}
        & $localPython (Join-Path $PSScriptRoot 'download_local_stores.py')
        if($LASTEXITCODE -ne 0){throw 'Could not download local storage runtimes.'}
    }
    foreach($path in @($serviceRoot,$pgData,$weedData)){New-Item -ItemType Directory -Path $path -Force | Out-Null}
    if(-not (Test-Path -LiteralPath (Join-Path $pgRoot 'bin\initdb.exe'))){
        New-Item -ItemType Directory -Path (Split-Path $pgRoot -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $sourcePgRoot -Destination (Split-Path $pgRoot -Parent) -Recurse -Force
    }
    if(-not (Test-Path -LiteralPath $weedExe)){
        New-Item -ItemType Directory -Path (Split-Path $weedExe -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $sourceWeedExe -Destination $weedExe -Force
    }
    if(-not (Test-Path -LiteralPath $credentialFile)){
        $pgPassword=([guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N'))
        $accessKey='risk'+[guid]::NewGuid().ToString('N').Substring(0,16)
        $secretKey=([guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllLines($credentialFile,@("PG_PASSWORD=$pgPassword","S3_ACCESS_KEY=$accessKey","S3_SECRET_KEY=$secretKey"),[Text.UTF8Encoding]::new($false))
    }
    $credentials=Read-Credentials
    if(-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))){
        $pwFile=Join-Path $serviceRoot 'pg-password.tmp'
        try{
            [IO.File]::WriteAllText($pwFile,$credentials.PG_PASSWORD,[Text.UTF8Encoding]::new($false))
            & (Join-Path $pgBin 'initdb.exe') -D $pgData -U risk_app --pwfile=$pwFile --encoding=UTF8 --locale=C --auth-host=scram-sha-256 --auth-local=scram-sha-256 | Out-Null
            if($LASTEXITCODE -ne 0){throw 'PostgreSQL initialization failed.'}
        }finally{Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue}
        Add-Content -LiteralPath (Join-Path $pgData 'postgresql.conf') -Value "`nlisten_addresses = '127.0.0.1'`nport = $pgPort`npassword_encryption = 'scram-sha-256'`n"
    }
    $config=@{identities=@(@{name='risk-agent';credentials=@(@{accessKey=$credentials.S3_ACCESS_KEY;secretKey=$credentials.S3_SECRET_KEY});actions=@('Admin','Read','Write')})}|ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText($s3Config,$config,[Text.UTF8Encoding]::new($false))
    Start-Stores
    $env:PGPASSWORD=$credentials.PG_PASSWORD
    & (Join-Path $pgBin 'psql.exe') -h 127.0.0.1 -p $pgPort -U risk_app -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='risk_agent'" | ForEach-Object {$databaseExists=$_}
    if($databaseExists -ne '1'){
        & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p $pgPort -U risk_app -E UTF8 risk_agent
        if($LASTEXITCODE -ne 0){throw 'Could not create risk_agent database.'}
    }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Set-EnvValue 'DB_BACKEND' 'postgres';Set-EnvValue 'PG_HOST' '127.0.0.1';Set-EnvValue 'PG_PORT' "$pgPort";Set-EnvValue 'PG_DATABASE' 'risk_agent';Set-EnvValue 'PG_USER' 'risk_app';Set-EnvValue 'PG_PASSWORD' $credentials.PG_PASSWORD
    Set-EnvValue 'STORAGE_BACKEND' 's3';Set-EnvValue 'S3_ENDPOINT' "127.0.0.1:$s3Port";Set-EnvValue 'S3_ACCESS_KEY' $credentials.S3_ACCESS_KEY;Set-EnvValue 'S3_SECRET_KEY' $credentials.S3_SECRET_KEY;Set-EnvValue 'S3_BUCKET' 'risk-agent';Set-EnvValue 'S3_SECURE' 'false';Set-EnvValue 'S3_REGION' 'us-east-1'
    Write-Output 'PostgreSQL and S3 object storage installed and started locally.'
    exit 0
}
if($Action -eq 'start'){Start-Stores;Write-Output 'Local stores started.';exit 0}
if($Action -eq 'stop'){
    if(Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION')){& (Join-Path $pgBin 'pg_ctl.exe') stop -D $pgData -m fast -w | Out-Null}
    if(Test-Path -LiteralPath $weedPid){$idValue=[IO.File]::ReadAllText($weedPid).Trim();if($idValue -match '^\d+$'){Stop-Process -Id ([int]$idValue) -ErrorAction SilentlyContinue};Remove-Item $weedPid -Force}
    Write-Output 'Local stores stopped.';exit 0
}
$pgStatus=& (Join-Path $pgBin 'pg_ctl.exe') status -D $pgData 2>$null
$weedStatus=if(Test-Path $weedPid){Get-Process -Id ([int][IO.File]::ReadAllText($weedPid).Trim()) -ErrorAction SilentlyContinue}else{$null}
Write-Output (ConvertTo-Json @{postgres=[bool]($LASTEXITCODE -eq 0);s3=[bool]$weedStatus})
