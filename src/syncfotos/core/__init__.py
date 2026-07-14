"""Nucli de lògica de SyncFotos."""

from .sync_core import (
	cache_path_for,
	count_files,
	data_a_path,
	default_cache_dir,
	load_cache,
	load_validated_cache,
	scan_directory,
	save_cache,
)
from .sync_outputs import build_missing_and_present, write_deletion_script, write_missing_report

