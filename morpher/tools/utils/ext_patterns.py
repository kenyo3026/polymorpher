import os
from pathlib import Path
from typing import List

# File patterns for build artifacts
EXT_PATTERNS_FOR_ARTIFACT = [
    ".gradle/",
    ".idea/",
    ".parcel-cache/",
    ".pytest_cache/",
    ".next/",
    ".nuxt/",
    ".sass-cache/",
    ".terraform/",
    ".terragrunt-cache/",
    ".vs/",
    ".vscode/",
    "Pods/",
    "__pycache__/",
    "bin/",
    "build/",
    "bundle/",
    "coverage/",
    "deps/",
    "dist/",
    "env/",
    "node_modules/",
    "obj/",
    "out/",
    "pkg/",
    "pycache/",
    "target/dependency/",
    "temp/",
    "vendor/",
    "venv/",
]

# File patterns for media files
EXT_PATTERNS_FOR_MEDIA_FILE = [
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.gif",
    "*.bmp",
    "*.ico",
    "*.webp",
    "*.tiff",
    "*.tif",
    "*.raw",
    "*.heic",
    "*.avif",
    "*.eps",
    "*.psd",
    "*.ttf",
    "*.otf",
    "*.woff",
    "*.woff2",
    "*.eot",
    "*.3gp",
    "*.aac",
    "*.aiff",
    "*.asf",
    "*.avi",
    "*.divx",
    "*.flac",
    "*.m4a",
    "*.m4v",
    "*.mkv",
    "*.mov",
    "*.mp3",
    "*.mp4",
    "*.mpeg",
    "*.mpg",
    "*.ogg",
    "*.opus",
    "*.rm",
    "*.rmvb",
    "*.vob",
    "*.wav",
    "*.webm",
    "*.wma",
    "*.wmv",
]

# File patterns for cache files
EXT_PATTERNS_FOR_CACHE_FILE = [
    "*.DS_Store",
    "*.bak",
    "*.cache",
    "*.crdownload",
    "*.dmp",
    "*.dump",
    "*.eslintcache",
    "*.lock",
    "*.log",
    "*.old",
    "*.part",
    "*.partial",
    "*.pyc",
    "*.pyo",
    "*.stackdump",
    "*.swo",
    "*.swp",
    "*.temp",
    "*.tmp",
    "*.Thumbs.db",
]

# File patterns for configuration files
EXT_PATTERNS_FOR_CONFIG_FILE = [
    "*.env*",
    "*.local",
    "*.development",
    "*.production"
]

# File patterns for large data files
EXT_PATTERNS_FOR_LARGE_DATA_FILE = [
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    "*.iso",
    "*.bin",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.dat",
    "*.dmg",
    "*.msi",
]

# File patterns for database files
EXT_PATTERNS_FOR_DATABASE_FILE = [
    "*.arrow",
    "*.accdb",
    "*.aof",
    "*.avro",
    "*.bak",
    "*.bson",
    "*.csv",
    "*.db",
    "*.dbf",
    "*.dmp",
    "*.frm",
    "*.ibd",
    "*.mdb",
    "*.myd",
    "*.myi",
    "*.orc",
    "*.parquet",
    "*.pdb",
    "*.rdb",
    "*.sql",
    "*.sqlite",
]

# File patterns for geospatial files
EXT_PATTERNS_FOR_GEOSPATIAL = [
    "*.shp",
    "*.shx",
    "*.dbf",
    "*.prj",
    "*.sbn",
    "*.sbx",
    "*.shp.xml",
    "*.cpg",
    "*.gdb",
    "*.mdb",
    "*.gpkg",
    "*.kml",
    "*.kmz",
    "*.gml",
    "*.geojson",
    "*.dem",
    "*.asc",
    "*.img",
    "*.ecw",
    "*.las",
    "*.laz",
    "*.mxd",
    "*.qgs",
    "*.grd",
    "*.csv",
    "*.dwg",
    "*.dxf",
]

# File patterns for log files
EXT_PATTERNS_FOR_LOG_FILE = [
    "*.error",
    "*.log",
    "*.logs",
    "*.npm-debug.log*",
    "*.out",
    "*.stdout",
    "yarn-debug.log*",
    "yarn-error.log*",
]

# Base exclude patterns (does not depend on file system)
EXT_PATTERNS_FOR_BASE_EXCLUDE = [
    ".git/",
    *EXT_PATTERNS_FOR_ARTIFACT,
    *EXT_PATTERNS_FOR_MEDIA_FILE,
    *EXT_PATTERNS_FOR_CACHE_FILE,
    *EXT_PATTERNS_FOR_CONFIG_FILE,
    *EXT_PATTERNS_FOR_LARGE_DATA_FILE,
    *EXT_PATTERNS_FOR_DATABASE_FILE,
    *EXT_PATTERNS_FOR_GEOSPATIAL,
    *EXT_PATTERNS_FOR_LOG_FILE,
]


def get_lfs_patterns(workspace_path: str) -> List[str]:
    """Get Git LFS file patterns"""
    try:
        attributes_path = Path(workspace_path) / ".gitattributes"
        
        if attributes_path.exists():
            with open(attributes_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")
                lfs_patterns = []
                
                for line in lines:
                    if "filter=lfs" in line:
                        pattern = line.split(" ")[0].strip()
                        lfs_patterns.append(pattern)
                
                return lfs_patterns
    except Exception:
        pass
    
    return []


def get_exclude_patterns(workspace_path: str) -> List[str]:
    """Get all exclude file patterns (including LFS)"""
    patterns = EXT_PATTERNS_FOR_BASE_EXCLUDE.copy()
    lfs_patterns = get_lfs_patterns(workspace_path)
    patterns.extend(lfs_patterns)
    return patterns
