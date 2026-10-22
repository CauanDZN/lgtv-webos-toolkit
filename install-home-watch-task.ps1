<#
Faz o home-watch.py (redireciona o botao Home da TV pro launcher) iniciar sozinho quando voce
liga este PC, e reiniciar se cair. So funciona enquanto o PC estiver ligado e na mesma rede da TV.

  .\install-home-watch-task.ps1 -TvHost 192.168.10.182     # instala
  .\install-home-watch-task.ps1 -Uninstall                 # remove

Ver se esta rodando:  Get-ScheduledTask "LG TV Home Watch" | Get-ScheduledTaskInfo
Ver o log:             Get-Content "$env:TEMP\lg-tv-home-watch.log" -Tail 20 -Wait
#>
param(
    [string]$TvHost = "192.168.10.182",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "LG TV Home Watch"

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Precisa rodar como Administrador: feche este PowerShell, abra de novo clicando com o botao direito no icone e escolhendo 'Executar como administrador', entre na pasta lg-webos de novo e rode o script."
    exit 1
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removido. O botao Home volta a abrir a home da LG."
    exit
}

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Here "webos-vibehack\home-watch.py"
if (-not (Test-Path $Script)) {
    Write-Error "Nao achei $Script. Rode este script de dentro da pasta lg-webos."
    exit 1
}

$Py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = (Get-Command python.exe).Source }  # fallback: abre uma janela de console

$Log = Join-Path $env:TEMP "lg-tv-home-watch.log"
# "cmd /c ... > log 2>&1" porque home-watch.py so imprime no stdout, sem opcao de arquivo de log.
$Action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"$Py`" -u `"$Script`" $TvHost >> `"$Log`" 2>&1" `
    -WorkingDirectory $Here
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries

try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
        -Description "Redireciona o botao Home da TV LG ($TvHost) para o launcher (webos-vibehack)" -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 2
    $info = Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo
    if ($info.LastTaskResult -ne 0 -and $info.LastTaskResult -ne 267009) {
        # 267009 = still running, that's the expected state for this long-lived task
        throw "A tarefa foi criada mas nao ficou rodando (codigo $($info.LastTaskResult)). Confira $Log."
    }
} catch {
    Write-Error "Falhou: $_"
    exit 1
}

Write-Host "Instalado e rodando de verdade (confirmado pelo Task Scheduler). Log: $Log"
Write-Host "Aperte Home no controle da TV para testar. Duas vezes em 3s mantem a home da LG."
