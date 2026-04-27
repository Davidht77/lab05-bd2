import math
import os
import struct

HEADER_SIZE = 4 * 3


def export_to_heap(csv_path: str, heap_path: str, record_format: str, page_size: int):
	if os.path.exists(heap_path):
		raise Exception("el archivo de destino ya existia")
	if not os.path.exists(csv_path):
		raise Exception("el csv no existe")
	types = record_format.split(' ')
	record_format = record_format.replace(' ', '')

	with open(heap_path, 'w+b') as file:
		csv = open(csv_path, 'r')
		csv.seek(0)
		regs = 0
		file.seek(HEADER_SIZE)
		for line in csv:
			regs += 1
			line = line[:-1]
			tup = line.split(',')
			for i in range(len(types)):
				if types[i] == 'i':
					tup[i] = int(tup[i])
				elif types[i] == 'f':
					tup[i] = float(tup[i])
				else:
					n = int(types[i][:-1])
					tup[i] = tup[i].ljust(n, ' ').encode()
			tup = tuple(tup)
			file.write(struct.pack(record_format, *tup))
		csv.close()
	write_header(heap_path, struct.calcsize(record_format), page_size, regs)


def write_header(heap_path: str, reg_size: int, page_size: int, regs: int):
	with open(heap_path, 'rb+') as f:
		f.seek(0)
		f.write(struct.pack('i', reg_size))
		f.write(struct.pack('i', page_size))
		f.write(struct.pack('i', regs))


def read_header(heap_path: str):
	with open(heap_path, 'rb') as f:
		f.seek(0)
		return struct.unpack('iii', f.read(12))


def read_page(heap_path: str, page_id: int, reg_format: str) -> list[tuple]:
	reg_size, page_size, regs = read_header(heap_path)
	rpp = page_size // reg_size
	offset = HEADER_SIZE + page_id * rpp * reg_size
	already = page_id * rpp
	to_read = min(rpp, regs - already)
	if to_read <= 0:
		return []
	records = []
	with open(heap_path, 'rb') as f:
		f.seek(offset)
		for _ in range(to_read):
			raw = f.read(reg_size)
			if len(raw) < reg_size:
				break
			records.append(struct.unpack(reg_format, raw))
	return records


def write_page(heap_path: str, page_id: int, records: list[tuple], record_format: str):
	reg_size, page_size, regs = read_header(heap_path)
	regs_per_page = page_size // reg_size
	page_offset = HEADER_SIZE + page_id * regs_per_page * reg_size
	with open(heap_path, 'rb+') as f:
		f.seek(page_offset)
		for reg in records:
			f.write(struct.pack(record_format, *reg))


def count_pages(heap_path: str) -> int:
	reg_size, page_size, regs = read_header(heap_path)
	regs_per_page = page_size // reg_size
	return math.ceil(regs / regs_per_page)


def total_pages(heap_path: str):
	return count_pages(heap_path)


def key_idx(sort_key):
	try:
		return int(sort_key)
	except ValueError:
		maps = {
			'id': 0, 'birth_date': 1, 'first_name': 2, 'last_name': 3, 'gender': 4, 'hire_date': 5,
			'employee_id': 0, 'department_id': 1, 'from_date': 2, 'to_date': 3,
		}
		if sort_key in maps:
			return maps[sort_key]
		raise ValueError(f"sort_key '{sort_key}' no reconocido")


def clean_value(value):
	if isinstance(value, bytes):
		return value.rstrip(b' \x00').decode()
	return value


def write_records_as_pages(records, reg_format, page_size, path):
	reg_size = struct.calcsize(reg_format)
	rpp = page_size // reg_size
	with open(path, 'wb') as f:
		for i in range(0, len(records), rpp):
			chunk = records[i:i + rpp]
			for rec in chunk:
				f.write(struct.pack(reg_format, *rec))
			f.write(b'\x00' * ((rpp - len(chunk)) * reg_size))


def read_temp_page(path, page_id, reg_format, page_size):
	reg_size = struct.calcsize(reg_format)
	rpp = page_size // reg_size
	offset = page_id * rpp * reg_size
	if offset >= os.path.getsize(path):
		return []
	records = []
	with open(path, 'rb') as f:
		f.seek(offset)
		for _ in range(rpp):
			raw = f.read(reg_size)
			if len(raw) < reg_size:
				break
			rec = struct.unpack(reg_format, raw)
			first = rec[0]
			is_pad = (isinstance(first, bytes) and first.strip(b'\x00') == b'') or \
			         (isinstance(first, (int, float)) and first == 0 and all(
				         (v == b'\x00' * len(v) if isinstance(v, bytes) else v == 0) for v in rec))
			if is_pad:
				break
			records.append(rec)
	return records
