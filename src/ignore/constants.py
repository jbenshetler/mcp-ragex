"""
Central configuration for ignore file processing
"""

# Single source of truth for ignore filename
# Future migration: change this to ".ragexignore"
IGNORE_FILENAME = ".mcpignore"

# Default exclusion patterns that apply globally
DEFAULT_EXCLUSIONS = [
    # Python
    ".venv/**",
    "venv/**",
    "env/**",
    ".env/**",
    "virtualenv/**",
    "__pycache__/**",
    "*.py[cod]",
    "*$py.class",
    "*.so",
    ".Python",
    "pip-log.txt",
    "pip-delete-this-directory.txt",
    ".mypy_cache/**",
    ".pytest_cache/**",
    ".tox/**",
    ".coverage",
    ".coverage.*",
    "htmlcov/**",
    ".hypothesis/**",
    "*.egg-info/**",
    "dist/**",
    "wheels/**",
    ".eggs/**",
    
    # JavaScript/TypeScript/Node.js
    "node_modules/**",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    "lerna-debug.log*",
    ".npm/**",
    ".yarn/**",
    ".pnp.*",
    ".yarn-integrity",
    "*.tsbuildinfo",
    
    # React/Frontend build artifacts
    "build/**",
    "dist/**",
    "out/**",
    ".next/**",
    ".nuxt/**",
    ".cache/**",
    ".parcel-cache/**",
    ".webpack/**",
    ".vuepress/dist/**",
    ".docusaurus/**",
    ".serverless/**",
    "public/build/**",
    
    # C/C++ build artifacts (CMake, Make, etc.)
    "build/**",
    "cmake-build-*/**",
    "CMakeFiles/**",
    "CMakeCache.txt",
    "*.cmake",
    "Makefile",
    "compile_commands.json",
    "*.o",
    "*.obj",
    "*.a",
    "*.lib",
    "*.so",
    "*.so.*",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.out",
    "*.app",
    
    # IDE and editor files
    ".vscode/**",
    ".idea/**",
    "*.swp",
    "*.swo",
    "*~",
    ".project",
    ".classpath",
    ".settings/**",
    "*.sublime-workspace",
    "*.sublime-project",
    
    # OS files
    ".DS_Store",
    ".DS_Store?",
    "._*",
    "Thumbs.db",
    "ehthumbs.db",
    "Desktop.ini",
    "$RECYCLE.BIN/**",
    
    # Logs and databases
    "*.log",
    "logs/**",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    
    # Testing
    ".nyc_output/**",
    "coverage/**",
    "*.lcov",
    ".grunt/**",
    
    # Package manager locks (usually tracked, but excluded from code analysis)
    # Uncomment if you want to exclude these:
    # "package-lock.json",
    # "yarn.lock",
    # "pnpm-lock.yaml",
    # "poetry.lock",
    # "Pipfile.lock",
    
    # Temporary files
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.backup",
    "*.old",
    
    # Version control
    ".git/**",
    ".svn/**",
    ".hg/**",
    ".bzr/**",
    
    # Documentation build
    "docs/_build/**",
    "site/**",
    "_site/**",
    ".jekyll-cache/**",
    ".sass-cache/**",
    
    # Environment files (often contain secrets)
    ".env",
    ".env.*",
    "!.env.example",
    "!.env.template",
    
    # Archives
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.rar",
    "*.7z",
    
    # Media files (usually not code)
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.mov",
    "*.mp4",
    "*.mp3",
    "*.wav",
]

# Limits for security and performance
MAX_IGNORE_FILE_SIZE = 1024 * 1024  # 1MB
MAX_PATTERNS_PER_FILE = 10000
MAX_CACHE_SIZE = 10000