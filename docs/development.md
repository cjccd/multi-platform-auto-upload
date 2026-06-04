# Development

## Run tests

```bash
python3 -m unittest -v tests.test_mpau_cli
```

## Verify CLI help

```bash
python3 mpau_cli.py --help
python3 mpau_cli.py douyin --help
python3 mpau_cli.py pdd --help
python3 mpau_cli.py tiktok --help
```

## Before publishing a fork

Make sure you do not publish local runtime data:

- no `cookies/`
- no `logs/`
- no real video files
- no `.venv/`
- no `__pycache__/`
- no QR code images
- no personal account or shop credentials
