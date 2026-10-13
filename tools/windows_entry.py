"""Windows GUI entry point with a packaged-runtime check."""
import json
import sys
import traceback
from pathlib import Path
from columns_ec2.main import main

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        receipt = Path(sys.argv[2]).resolve()
        try:
            from tools.smoke_test import main as smoke
            from columns_ec2.gui.app import create_app
            smoke()
            app = create_app()
            app.withdraw()
            app.update_idletasks()
            app.destroy()
            receipt.write_text(json.dumps({"status": "ok", "checks": ["runtime", "calculation", "tkinter"]}), encoding="utf-8")
        except Exception:
            receipt.write_text(traceback.format_exc(), encoding="utf-8")
            sys.exit(1)
    else:
        main()
