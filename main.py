import os
import tempfile

from heap_file import export_to_heap
from external_sort import external_sort
from external_hashing import external_hash_group_by

E_csv='employee.csv'
D_csv='department_employee.csv'
E_format='i 10s 15s 15s 1s 10s'
D_format='i 5s 10s 10s'
E_heap=os.path.join('data', 'employee.bin')
D_heap=os.path.join('data', 'department_employee.bin')
Buffer_Size=64 * 1000

PageSize=4096


def prepare_heap_files():
	os.makedirs('data', exist_ok=True)
	if not os.path.exists(E_heap):
		export_to_heap(E_csv, E_heap, E_format, PageSize)
	if not os.path.exists(D_heap):
		export_to_heap(D_csv, D_heap, D_format, PageSize)


def print_metrics_row(name, buffer_size, units, phase1, phase2, total, io_total):
	print(
		f"{name:<18} {buffer_size // 1024:>6} KB "
		f"{buffer_size // PageSize:>4} pag "
		f"{units:>8} "
		f"{phase1:>10.4f} "
		f"{phase2:>10.4f} "
		f"{total:>10.4f} "
		f"{io_total:>8}"
	)


def run_lab_2_4():
	prepare_heap_files()
	buffer_sizes = [64 * 1024, 128 * 1024, 256 * 1024]

	print("Algoritmo          Buffer     M    Runs/Part   Fase 1     Fase 2      Total       I/O")
	for buffer_size in buffer_sizes:
		tmp_sort = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
		tmp_sort.close()
		sort_metrics = external_sort(E_heap, tmp_sort.name, E_format, PageSize, buffer_size, 'hire_date')
		os.remove(tmp_sort.name)

		hash_metrics = external_hash_group_by(D_heap, D_format, PageSize, buffer_size, 'from_date')

		print_metrics_row(
			"External Sort",
			buffer_size,
			sort_metrics['runs_generated'],
			sort_metrics['time_phase1_sec'],
			sort_metrics['time_phase2_sec'],
			sort_metrics['time_total_sec'],
			sort_metrics['pages_read'] + sort_metrics['pages_written'],
		)
		print_metrics_row(
			"External Hashing",
			buffer_size,
			hash_metrics['partitions_created'],
			hash_metrics['time_phase1_sec'],
			hash_metrics['time_phase2_sec'],
			hash_metrics['time_total_sec'],
			hash_metrics['pages_read'] + hash_metrics['pages_written'],
		)

	result = external_hash_group_by(D_heap, D_format, PageSize, Buffer_Size, 'from_date')['result']
	print(f"\nGrupos encontrados para from_date: {len(result)}")
	print("Primeros 10 grupos:", sorted(result.items())[:10])


if __name__ == '__main__':
	run_lab_2_4()
