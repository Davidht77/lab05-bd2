import os
import struct
import tempfile
import time

from heap_file import clean_value, key_idx, read_header, read_page, read_temp_page, total_pages


def append_partition_record(file, buffer, record, reg_format, reg_size, rpp):
	buffer.append(record)
	if len(buffer) < rpp:
		return 0
	for rec in buffer:
		file.write(struct.pack(reg_format, *rec))
	buffer.clear()
	return 1


def partition_data(heap_path: str, reg_format: str, page_size: int, buffer_size: int, group_key: str) -> list[str]:
	reg_size, _, _ = read_header(heap_path)
	B = buffer_size // page_size
	if B < 2:
		raise ValueError("buffer_size debe permitir al menos 2 paginas")
	k = B - 1
	ki = key_idx(group_key)
	rpp = page_size // reg_size
	total_pgs = total_pages(heap_path)
	tmp_dir = tempfile.mkdtemp(prefix='ext_hash_')
	partition_paths = [os.path.join(tmp_dir, f'part_{i:04d}.bin') for i in range(k)]
	files = [open(path, 'wb') for path in partition_paths]
	buffers = [[] for _ in range(k)]
	pages_read, pages_written = 0, 0

	try:
		for page_id in range(total_pgs):
			page = read_page(heap_path, page_id, reg_format)
			pages_read += 1
			for rec in page:
				key = clean_value(rec[ki])
				pid = hash(key) % k
				pages_written += append_partition_record(
					files[pid], buffers[pid], rec, reg_format, reg_size, rpp
				)

		for i in range(k):
			if buffers[i]:
				for rec in buffers[i]:
					files[i].write(struct.pack(reg_format, *rec))
				files[i].write(b'\x00' * ((rpp - len(buffers[i])) * reg_size))
				pages_written += 1
				buffers[i].clear()
	finally:
		for f in files:
			f.close()

	partition_data.pages_read = pages_read
	partition_data.pages_written = pages_written
	return partition_paths


def aggregate_partitions(partition_paths: list[str], reg_format: str, page_size: int, buffer_size: int, group_key: str) -> dict:
	ki = key_idx(group_key)
	result = {}
	pages_read = 0

	for path in partition_paths:
		local_hash = {}
		page_id = 0
		while True:
			page = read_temp_page(path, page_id, reg_format, page_size)
			if not page:
				break
			pages_read += 1
			page_id += 1
			for rec in page:
				key = clean_value(rec[ki])
				local_hash[key] = local_hash.get(key, 0) + 1

		for key, count in local_hash.items():
			result[key] = result.get(key, 0) + count

	aggregate_partitions.pages_read = pages_read
	return result


def external_hash_group_by(heap_path: str, reg_format: str, page_size: int, buffer_size: int, group_key: str) -> dict:
	t0 = time.perf_counter()

	t1 = time.perf_counter()
	partition_paths = partition_data(heap_path, reg_format, page_size, buffer_size, group_key)
	t1 = time.perf_counter() - t1
	pr1 = getattr(partition_data, 'pages_read', 0)
	pw1 = getattr(partition_data, 'pages_written', 0)

	t2 = time.perf_counter()
	result = aggregate_partitions(partition_paths, reg_format, page_size, buffer_size, group_key)
	t2 = time.perf_counter() - t2
	pr2 = getattr(aggregate_partitions, 'pages_read', 0)

	for path in partition_paths:
		try:
			os.remove(path)
		except OSError:
			pass
	try:
		os.rmdir(os.path.dirname(partition_paths[0]))
	except (OSError, IndexError):
		pass

	return {
		'result': result,
		'partitions_created': len(partition_paths),
		'pages_read': pr1 + pr2,
		'pages_written': pw1,
		'time_phase1_sec': round(t1, 4),
		'time_phase2_sec': round(t2, 4),
		'time_total_sec': round(time.perf_counter() - t0, 4),
	}
