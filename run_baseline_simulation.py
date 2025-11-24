import xml.etree.ElementTree as ET
from xml.dom import minidom
import pathlib
import argparse
import subprocess
from multiprocessing import Pool
import os


py_path = pathlib.Path(__file__)

def create_sumo_config(sim_start=0, sim_end=86400,seed=0, eval_start=0, eval_end=86400):

    # Create root element
    root = ET.Element('configuration')
    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/sumoConfiguration.xsd')

    # Input section
    input_elem = ET.SubElement(root, 'input')
    ET.SubElement(input_elem, 'net-file', value='../berlin.net.xml.gz')
    ET.SubElement(input_elem, 'route-files', value=f'../berlin_s_{seed}.rou.gz')
    ET.SubElement(input_elem, 'additional-files', value=f'../edge_data_cfg/berlin_s_{seed}_{eval_start}_{eval_end}_baseline_edgedata_cfg.add.xml')

    # Output section
    output_elem = ET.SubElement(root, 'output')
    ET.SubElement(output_elem, 'output-prefix', value=f'../output/berlin_s_{seed}_baseline_{sim_start}_{sim_end}_')
    ET.SubElement(output_elem, 'log', value='console.log')
    ET.SubElement(output_elem, 'summary-output', value='summary.xml')
    ET.SubElement(output_elem, 'statistic-output', value='statistics.xml')
    ET.SubElement(output_elem, 'vehroute-output', value='vehroute.xml.gz')
    ET.SubElement(output_elem, 'vehroute-output.route-length', value='true')
    ET.SubElement(output_elem, 'stop-output', value='stop.xml.gz')
    ET.SubElement(output_elem, 'tripinfo-output', value='tripinfo.xml.gz')

    # Time section
    time_elem = ET.SubElement(root, 'time')
    ET.SubElement(time_elem, 'begin', value='21600')
    ET.SubElement(time_elem, 'end', value='86400.0')

    # Processing section
    processing_elem = ET.SubElement(root, 'processing')
    ET.SubElement(processing_elem, 'route-steps', value='200')
    ET.SubElement(processing_elem, 'no-internal-links', value='false')
    ET.SubElement(processing_elem, 'ignore-junction-blocker', value='20')
    ET.SubElement(processing_elem, 'time-to-teleport', value='120.0')
    ET.SubElement(processing_elem, 'time-to-teleport.highways', value='0')
    ET.SubElement(processing_elem, 'eager-insert', value='false')

    # Random number section
    random_elem = ET.SubElement(root, 'random_number')
    ET.SubElement(random_elem, 'random', value='false')
    ET.SubElement(random_elem, 'seed', value='251920')

    # Create XML tree and add declaration/comment
    tree = ET.ElementTree(root)

    # Pretty print
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")

    # Add comment after XML declaration

    output_path = py_path.parent/"sumo_cfg"/f'berlin_s_{seed}_{eval_start}_{eval_end}_baseline.sumocfg'
    # Write to file
    with open(output_path, 'w', encoding='UTF-8') as f:
        f.write(xml_str)

    print(f'SUMO configuration file created at: {output_path}')

    return output_path

def create_edge_data_additional(
    seed=0,
    eval_start=0,
    eval_end=86400,
    period=3600,
    with_internal=True,
    exclude_empty=True,
    min_samples=2,
    track_vehicles=True,
):
    # Root element
    additional = ET.Element("additional")

    # EdgeData element
    edge_data = ET.SubElement(additional, "edgeData")
    edge_data.set("id", f"edgedata_s_{seed}_{eval_start}_{eval_end}")
    edge_data.set("begin", str(eval_start))
    edge_data.set("end", str(eval_end))
    edge_data.set("file", f"berlin_s_{seed}_{eval_start}_{eval_end}_baseline_edgedata.xml")
    edge_data.set("period", str(period))
    edge_data.set("withInternal", str(with_internal).lower())
    edge_data.set("excludeEmpty", str(exclude_empty).lower())
    edge_data.set("minSamples", str(min_samples))
    edge_data.set("trackVehicles", str(track_vehicles).lower())
    output_path = py_path.parent/"edge_data_cfg"/ f"berlin_s_{seed}_{eval_start}_{eval_end}_baseline_edgedata_cfg.add.xml"
    # Write to file (pretty print)
    tree = ET.ElementTree(additional)
    ET.indent(tree, space="    ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


    def run_sumo_simulation(cfg_path):
        """
        Run a single SUMO simulation given a configuration file path.
        
        Args:
            cfg_path: Path to the .sumocfg file
        
        Returns:
            Tuple of (cfg_path, return_code)
        """
        try:
            result = subprocess.run(
                ['sumo', '-c', str(cfg_path)],
                capture_output=True,
                text=True,
                check=False
            )
            print(f"Completed: {cfg_path} (return code: {result.returncode})")
            return (cfg_path, result.returncode)
        except Exception as e:
            print(f"Error running {cfg_path}: {e}")
            return (cfg_path, -1)


    def run_sumo_configs_parallel(cfg_paths, n_processes=4):
        """
        Run multiple SUMO configuration files in parallel.
        
        Args:
            cfg_paths: List of paths to .sumocfg files
            n_processes: Number of parallel processes to use
        
        Returns:
            List of tuples (cfg_path, return_code)
        """
        print(f"Running {len(cfg_paths)} simulations on {n_processes} processes...")
        
        with Pool(processes=n_processes) as pool:
            results = pool.map(run_sumo_simulation, cfg_paths)
        
        # Summary
        successful = sum(1 for _, code in results if code == 0)
        failed = len(results) - successful
        print(f"\nCompleted: {successful} successful, {failed} failed")
        
        return results



if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Create SUMO configuration files')
    parser.add_argument('--s', '--seeds', type=lambda s: [int(item) for item in s.split(',')], default=[0], help='Seeds for simulation (comma-separated, e.g., 0,1,2)')
    parser.add_argument('--evaluation_interval', type=int, default=3600, help='Interval Length [seconds]')
    parser.add_argument("--warmup_time", type=int, default=3600, help="Warmup time in seconds")
    parser.add_argument("--cooldown_time", type=int, default=0, help="Cooldown time in seconds")
    parser.add_argument('--processes', type=int, default=4, help='Number of parallel processes to run simulations')

    args = parser.parse_args()
    

    sumo_cfg_paths = []
    for seed in args.s:
        for eval_start in range(0, 24*3600, args.evaluation_interval):
            eval_end = eval_start + args.evaluation_interval
            sim_start = max(0, eval_start - args.warmup_time)
            sim_end = min(24*3600, eval_end + args.cooldown_time)
            sumo_cfg_path = create_sumo_config(sim_start=sim_start, sim_end=sim_end, seed=seed, eval_start=eval_start, eval_end=eval_end)
            sumo_cfg_paths.append(sumo_cfg_path)
            create_edge_data_additional(seed=seed, eval_start=eval_start, eval_end=eval_end,period=args.evaluation_interval)



    results = run_sumo_configs_parallel(sumo_cfg_paths, n_processes=args.processes)
    for cfg_path, return_code in results:
        if return_code != 0:
            print(f"Simulation failed for config: {cfg_path}")
    
