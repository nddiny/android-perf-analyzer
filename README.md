# Android Performance Analyzer

AI-powered Android performance log analyzer. Analyzes CPU, Memory, Battery, Network, Startup, and UI performance issues from log files.

## Installation

```bash
git clone https://github.com/nddiny/android-perf-analyzer.git
cd android-perf-analyzer
pip install -r requirements.txt
```

## Usage

### Python Script

```bash
# Basic usage
python analyzer.py /path/to/perf_logs.zip

# Save report to file
python analyzer.py /path/to/perf_logs.zip -o report.md

# Quiet mode
python analyzer.py /path/to/perf_logs.zip -q
```

### Claude Code Skill

```bash
/android-perf-analyzer
```

Then provide the path to your performance log zip file.

## Features

- **CPU Analysis**: Method tracing, frame time, input latency
- **Memory Analysis**: GC events, memory leaks, OOM detection
- **Battery Analysis**: Wakelock issues, background drain, sensor usage
- **Network Analysis**: Bandwidth usage, large transfers, retries
- **Startup Analysis**: Cold/warm start, DEX loading, ContentProvider init
- **UI Analysis**: Frame drops, overdraw, layout issues

## Supported Log Files

The analyzer automatically detects and parses:
- `*.trace` - Method traces
- `*.systrace` - Systrace files
- `meminfo*` - Memory info
- `batterystats*` - Battery statistics
- `*.hprof` - Heap dumps
- `*gfx*` - GPU/Frame logs
- `*network*` - Network logs
- `*startup*` / `*boot*` - Startup logs
- `*.txt` - Logcat and other text logs

## Output

The analyzer outputs a structured report with issues ranked by severity:

| Severity | Description |
|----------|-------------|
| 🔴 Critical | Immediate action required (crashes, ANR) |
| 🟠 High | Significant user impact |
| 🟡 Medium | Moderate impact, consider fixing |
| 🟢 Low | Minor impact, optimization opportunities |

## Examples

```bash
# Analyze performance logs
python analyzer.py ./logs/app_perf_20240101.zip

# Generate markdown report
python analyzer.py ./logs/app_perf.zip -o analysis_report.md
```

## Requirements

- Python 3.7+
- Standard library modules: `os`, `sys`, `re`, `zipfile`, `argparse`, `pathlib`

No external dependencies required.
