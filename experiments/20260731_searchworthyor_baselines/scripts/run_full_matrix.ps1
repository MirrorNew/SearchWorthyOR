param(
    [string]$DatasetRoot = '<DATASET_ROOT>',
    [string]$ExperimentRoot = '<EXPERIMENT_ROOT>',
    [string]$Python = '<PYTHON>',
    [string]$Model = 'gpt-5.6',
    [string]$ReasoningEffort = 'high',
    [int]$Limit = 0,
    [switch]$IncludeOracle
)

$ErrorActionPreference = 'Stop'
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
}
if (-not (Test-Path -LiteralPath $DatasetRoot)) {
    throw "Dataset not found: $DatasetRoot"
}
if (-not ($env:OPENOR_API_KEY -or $env:OPENAI_API_KEY)) {
    throw 'Missing OPENOR_API_KEY or OPENAI_API_KEY.'
}
if (-not ($env:OPENOR_BASE_URL -or $env:OPENAI_BASE_URL)) {
    throw 'Missing OPENOR_BASE_URL or OPENAI_BASE_URL.'
}

$scripts = Join-Path $ExperimentRoot 'scripts'
$runs = Join-Path $ExperimentRoot 'runs\api_full'
$results = Join-Path $ExperimentRoot 'results\api_full'
$conditions = @('no_search', 'corpus_search')
if ($IncludeOracle) {
    $conditions += 'oracle_evidence'
}
$limitArgs = @()
if ($Limit -gt 0) {
    $limitArgs = @('--limit', $Limit)
}

foreach ($baseline in @('gpt56_one_shot', 'optimus_prompt', 'chain_of_experts')) {
    foreach ($condition in $conditions) {
        & $Python (Join-Path $scripts 'run_prompt_baselines.py') `
            --baseline $baseline `
            --condition $condition `
            --dataset-root $DatasetRoot `
            --output-dir $runs `
            --model $Model `
            --reasoning-effort $ReasoningEffort `
            --overwrite `
            @limitArgs
        if ($LASTEXITCODE -ne 0) {
            throw "$baseline $condition runner failed with exit code $LASTEXITCODE"
        }
        $submission = Join-Path $runs "$baseline\$condition\submissions.jsonl"
        $score = Join-Path $results "${baseline}_${condition}.json"
        & $Python (Join-Path $scripts 'score_submissions.py') `
            --dataset-root $DatasetRoot `
            --submissions $submission `
            --output $score
        if ($LASTEXITCODE -ne 0) {
            throw "$baseline $condition scoring failed with exit code $LASTEXITCODE"
        }
    }
}

foreach ($condition in $conditions) {
    & $Python (Join-Path $scripts 'run_optiminer_searchworthyor.py') `
        --condition $condition `
        --dataset-root $DatasetRoot `
        --output-dir $runs `
        --model $Model `
        --reasoning-effort $ReasoningEffort `
        --overwrite `
        @limitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "optiminer_training_free $condition runner failed with exit code $LASTEXITCODE"
    }
    $submission = Join-Path $runs "optiminer_training_free\$condition\submissions.jsonl"
    $score = Join-Path $results "optiminer_training_free_${condition}.json"
    & $Python (Join-Path $scripts 'score_submissions.py') `
        --dataset-root $DatasetRoot `
        --submissions $submission `
        --output $score
    if ($LASTEXITCODE -ne 0) {
        throw "optiminer_training_free $condition scoring failed with exit code $LASTEXITCODE"
    }
}

Write-Output "Completed matrix. Results: $results"
