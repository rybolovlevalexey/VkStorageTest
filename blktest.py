import argparse
import subprocess
import json
import os
import sys


class BlockDevicePerformanceTest:
    def __init__(self, name, filename, rw, iodepth):
        self.name = name
        self.filename = filename
        self.rw = rw
        self.iodepth = iodepth

    def run_fio_test(self):
        command = [
            'fio',
            '--ioengine=libaio',
            '--direct=1',
            '--bs=4k',
            '--size=1G',
            '--numjobs=1',
            f'--name={self.name}',
            f'--filename={self.filename}',
            f'--rw={self.rw}',
            f'--iodepth={self.iodepth}',
            '--output-format=json'
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return result.stdout

    def parse_latency(self, output):
        """
        Парсит вывод Fio и извлекает среднюю задержку (latency) для указанной операции.
        """
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            print(f"Ошибка при декодировании JSON: {e}")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        # Проверка данных на корректность структуры
        if not isinstance(data, dict) or 'jobs' not in data:
            print(f"Некорректный формат вывода Fio: отсутствует ключ 'jobs'")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        if not isinstance(data['jobs'], list) or len(data['jobs']) == 0:
            print(f"Некорректный формат вывода Fio: 'jobs' должен быть непустым списком")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        job = data['jobs'][0]
        if 'job options' not in job or 'rw' not in job['job options']:
            print(f"Некорректный формат вывода Fio: отсутствует ключ 'job options' или 'rw'")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        if self.rw == 'randread':
            operation_key = 'read'
        elif self.rw == 'randwrite':
            operation_key = 'write'
        else:
            print(f"Неподдерживаемая операция: {self.rw}")
            sys.exit(1)

        # Проверка наличия данных для операции
        if operation_key not in job:
            print(f"Некорректный формат вывода Fio: отсутствует ключ '{operation_key}' в данных job")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        if 'lat_ns' not in job[operation_key] or 'mean' not in job[operation_key]['lat_ns']:
            print(f"Некорректный формат вывода Fio: отсутствует ключ 'lat_ns' или 'mean'")
            print(f"Вывод Fio: {output}")
            sys.exit(1)

        return job[operation_key]['lat_ns']['mean']


def generate_gnuplot_script(iodepths, latencies_randread, latencies_randwrite, output_file):
    """
    Генерирует скрипт для Gnuplot.
    """
    script = f"""
    set terminal pngcairo size 800,600 enhanced font 'Verdana,10'
    set output '{output_file}'
    set title "Latency vs I/O Depth"
    set xlabel "I/O Depth"
    set ylabel "Latency (ns)"
    set grid
    plot '-' with lines title 'randread', '-' with lines title 'randwrite'
    """

    # данные для randread
    for iodepth, latency in zip(iodepths, latencies_randread):
        script += f"{iodepth} {latency}\n"
    script += "e\n"

    # данные для randwrite
    for iodepth, latency in zip(iodepths, latencies_randwrite):
        script += f"{iodepth} {latency}\n"
    script += "e\n"
    return script


def main():
    parser = argparse.ArgumentParser(description='Run block device performance tests.')
    parser.add_argument('--name', required=True, help='Name of the test')
    parser.add_argument('--filename', required=True, help='Path to the file to test')
    parser.add_argument('--output', required=True, help='Path to save the output graph')
    args = parser.parse_args()

    iodepths = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    latencies_randread = []
    latencies_randwrite = []

    for iodepth in iodepths:
        block_dev_perf_test_write = BlockDevicePerformanceTest(
            args.name, args.filename, 'randwrite', iodepth)
        output = block_dev_perf_test_write.run_fio_test()
        latencies_randread.append(block_dev_perf_test_write.parse_latency(output))

        block_dev_perf_test_read = BlockDevicePerformanceTest(
            args.name, args.filename, 'randread', iodepth)
        output = block_dev_perf_test_read.run_fio_test()
        latencies_randwrite.append(block_dev_perf_test_read.parse_latency(output))

    # Генерация скрипта для Gnuplot
    gnuplot_script = generate_gnuplot_script(iodepths, latencies_randread, latencies_randwrite, args.output)

    # Сохранение скрипта во временный файл
    script_file = 'gnuplot_script.gp'
    with open(script_file, 'w') as f:
        f.write(gnuplot_script)

    # Запуск Gnuplot
    subprocess.run(['gnuplot', script_file])

    # Удаление временного файла скрипта
    os.remove(script_file)


if __name__ == '__main__':
    main()