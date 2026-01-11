#!/usr/bin/env python3
"""
Run the EAS Webapp development server.
"""

import sys
import os

# add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.web import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='127.0.0.1', port=5000)
