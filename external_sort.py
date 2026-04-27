import heapq
import math
import os
import shutil
import struct
import tempfile
import time

from heap_file import HEADER_SIZE, key_idx, read_header, read_page, read_temp_page, total_pages, write_records_as_pages


def generate_runs(heap_path: str, reg_format: str, page_size: int, buffer_size: int, sort_key: str) -> list[str]:
	reg_size, _, _ = read_header(heap_path)
	B = buffer_size // page_size
	ki = key_idx(sort_key)
	total_pgs = total_pages(heap_path)
	run_paths, pages_read, pages_written = [], 0, 0
	tmp_dir = tempfile.mkdtemp(prefix='ext_sort_')
	for start in range(0, total_pgs, B):
		buf = []
		for pg in range(start, min(start + B, total_pgs)):
			buf.extend(read_page(heap_path, pg, reg_format))
			pages_read += 1
		if not buf:
			continue
		buf.sort(key=lambda r: r[ki])
		path = os.path.join(tmp_dir, f'run_{len(run_paths):04d}.bin')
		write_records_as_pages(buf, reg_format, page_size, path)
		run_paths.append(path)
		pages_written += math.ceil(len(buf) / (page_size // reg_size))
	generate_runs.pages_read = pages_read
	generate_runs.pages_written = pages_written
	return run_paths


def multiway_merge(run_paths: list[str], output_path: str, reg_format: str, page_size: int, buffer_size: int, sort_key: str):
	reg_size = struct.calcsize(reg_format)
	rpp = page_size // reg_size
	ki = key_idx(sort_key)
	cur_pg = [0] * len(run_paths)
	bufs = [[] for _ in run_paths]
	pos = [0] * len(run_paths)
	pages_read, pages_written = 0, 0

	def load(i):
		nonlocal pages_read
		pg = read_temp_page(run_paths[i], cur_pg[i], reg_format, page_size)
		cur_pg[i] += 1
		if not pg:
			return False
		bufs[i], pos[i] = pg, 0
		pages_read += 1
		return True

	h = []
	for i in range(len(run_paths)):
		if load(i):
			rec = bufs[i][pos[i]]
			heapq.heappush(h, (rec[ki], i, rec))

	out_buf = []
	with open(output_path, 'r+b') as f:
		f.seek(HEADER_SIZE)

		def flush():
			nonlocal pages_written
			for s in range(0, len(out_buf), rpp):
				chunk = out_buf[s:s + rpp]
				for rec in chunk:
					f.write(struct.pack(reg_format, *rec))
				f.write(b'\x00' * ((rpp - len(chunk)) * reg_size))
				pages_written += 1

		while h:
			_, i, rec = heapq.heappop(h)
			out_buf.append(rec)
			if len(out_buf) >= rpp:
				flush()
				out_buf.clear()
			pos[i] += 1
			if pos[i] >= len(bufs[i]):
				if load(i):
					nr = bufs[i][pos[i]]
					heapq.heappush(h, (nr[ki], i, nr))
			else:
				nr = bufs[i][pos[i]]
				heapq.heappush(h, (nr[ki], i, nr))

		if out_buf:
			flush()

	multiway_merge.pages_read = pages_read
	multiway_merge.pages_written = pages_written


def external_sort(heap_path: str, output_path: str, reg_format: str, page_size: int, buffer_size: int, sort_key: str) -> dict:
	if os.path.abspath(heap_path) != os.path.abspath(output_path):
		shutil.copyfile(heap_path, output_path)

	t0 = time.perf_counter()

	t1 = time.perf_counter()
	run_paths = generate_runs(heap_path, reg_format, page_size, buffer_size, sort_key)
	t1 = time.perf_counter() - t1
	pr1 = getattr(generate_runs, 'pages_read', 0)
	pw1 = getattr(generate_runs, 'pages_written', 0)

	t2 = time.perf_counter()
	multiway_merge(run_paths, output_path, reg_format, page_size, buffer_size, sort_key)
	t2 = time.perf_counter() - t2
	pr2 = getattr(multiway_merge, 'pages_read', 0)
	pw2 = getattr(multiway_merge, 'pages_written', 0)

	for rp in run_paths:
		try:
			os.remove(rp)
		except OSError:
			pass
	try:
		os.rmdir(os.path.dirname(run_paths[0]))
	except (OSError, IndexError):
		pass

	return {
		'runs_generated': len(run_paths),
		'pages_read': pr1 + pr2,
		'pages_written': pw1 + pw2,
		'time_phase1_sec': round(t1, 4),
		'time_phase2_sec': round(t2, 4),
		'time_total_sec': round(time.perf_counter() - t0, 4),
	}
