import socket
import gi
from gi.repository import Notify
import statistics
from time import sleep
import toml
import ipaddress
from loguru import logger
import time
import ipfs_api
import subprocess
import re
import os
import sys

# how many seconds to wait before
# giving up on a ping operation and applying IPFS limitations
PING_COMMAND_TIMEOUT_S = 2

# upper and lower thresholds for applying/removing IPFS limitations
PING_LIMIT_THRESHOLD_MS = 40
PING_UNLIMIT_THRESHOLD_MS = 30
PING_NOTIFY_THRESHOLD_MS = 300
MAX_PEERS_COUNT = 800

PING_TARGET = "8.8.8.8"
# number of pings to average when compiling latency metrics
PING_SAMPLE_COUNT = 10
WINDOW_SIZE = 5
PING_INTERVAL = 1.0  # seconds
# path of the file to which to write logs
LOG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "IPFS_Ping_Monitor.csv"
)
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "config.toml")

# Default whitelist and blacklist
DEFAULT_WHITELIST = [
    "127.0.0.0/8",
    "192.168.0.0/16",
    "172.16.0.0/12",
    "10.0.0.0/8",
]
DEFAULT_BLACKLIST = []

# Load configuration from a TOML file


def load_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        toml.dump(
            {"whitelist": DEFAULT_WHITELIST, "bloacklist": DEFAULT_BLACKLIST},
            open(CONFIG_FILE_PATH, "w+"),
        )
    try:
        config = toml.load(CONFIG_FILE_PATH)
        whitelist = config.get("whitelist", DEFAULT_WHITELIST)
        blacklist = config.get("blacklist", DEFAULT_BLACKLIST)
        logger.warning("Loaded blacklist and whitelist from config.")
    except Exception as e:
        logger.warning(f"Failed to load config: {e}, using defaults.")
        whitelist = DEFAULT_WHITELIST
        blacklist = DEFAULT_BLACKLIST
    return whitelist, blacklist


whitelist, blacklist = load_config()
for multiaddr in ipfs_api.client._http_client.bootstrap.list()["Peers"]:
    if "/" not in multiaddr:
        continue
    parts = multiaddr.split("/")
    while "" in parts:
        parts.remove("")
    scheme = parts[0]
    address = parts[1]
    ip_address = None
    match scheme:
        case "ip4":
            ip_address = address
        case "ip6":
            print("Not filtering IPv6...")
        case "dnsaddr":
            try:
                ip_address = socket.gethostbyname(address)
            except socket.gaierror:
                print(f"Failed to resolve domain: {address}")
        case _:
            print(f"Failed to parse multiaddr: {multiaddr}")
    if ip_address:
        whitelist.append(f"{ip_address}/32")
print("\nWhitelist:")
for net_addr in whitelist:
    print(f"  {net_addr}")


def get_complement_cidrs(allowed_cidrs, blocked_cidrs):
    """Calculate CIDR blocks that exclude `allowed_cidrs` and include `blocked_cidrs`."""
    full_range = ipaddress.IPv4Network("0.0.0.0/0")
    allowed = [ipaddress.IPv4Network(cidr) for cidr in allowed_cidrs]
    blocked = [ipaddress.IPv4Network(cidr) for cidr in blocked_cidrs]

    excluded_ranges = set(allowed) - set(blocked)

    result_ranges = [full_range]
    for exclude in sorted(excluded_ranges, key=lambda net: net.prefixlen, reverse=True):
        temp_ranges = []
        for rng in result_ranges:
            # Ensure the excluded range is within the current range
            if exclude.subnet_of(rng):
                temp_ranges.extend(rng.address_exclude(exclude))
            else:
                temp_ranges.append(rng)
        result_ranges = temp_ranges

    return result_ranges


def apply_strict_filters():
    """Apply IPFS filters to block all IPs except the whitelisted ones."""
    try:
        logger.info("Applying strict filters")
        remove_all_filters()

        filters_to_apply = get_complement_cidrs(whitelist, blacklist)
        multi_addr_filters = [
            f"/ip4/{cidr.network_address}/ipcidr/{cidr.prefixlen}"
            for cidr in filters_to_apply
        ]
        for multi_addr in multi_addr_filters:
            logger.debug(f"Adding filter: {multi_addr}")
            ipfs_api.add_swarm_filter(multi_addr)
    except ipfs_api.ipfshttpclient.exceptions.ErrorResponse:
        # this error always gets thrown, isn't a problem
        pass
    except ipfs_api.ipfshttpclient.exceptions.ConnectionError as e:
        logger.error(f"ConnectionError: {e}")


def remove_all_filters():
    """Remove all currently applied IPFS filters."""
    try:
        logger.info("Removing all filters")
        filters = ipfs_api.get_swarm_filters()
        for filter_entry in filters:
            logger.debug(f"Removing filter: {filter_entry}")
            ipfs_api.rm_swarm_filter(filter_entry)
    except ipfs_api.ipfshttpclient.exceptions.ErrorResponse:
        # this error always gets thrown, isn't a problem
        pass
    except ipfs_api.ipfshttpclient.exceptions.ConnectionError as e:
        logger.error(f"ConnectionError: {e}")


def remove_strict_filters():
    """Remove all filters and apply blacklist as new filters."""
    try:
        logger.info("Removing strict filters and applying blacklist")
        remove_all_filters()
        for cidr in blacklist:
            multi_addr = f"/ip4/{cidr.network_address}/ipcidr/{cidr.prefixlen}"
            logger.info(f"Blacklisting: {multi_addr}")
            ipfs_api.add_swarm_filter(multi_addr)
    except ipfs_api.ipfshttpclient.exceptions.ErrorResponse:
        # this error always gets thrown, isn't a problem
        pass
    except ipfs_api.ipfshttpclient.exceptions.ConnectionError as e:
        logger.error(f"ConnectionError: {e}")


def are_strict_filters_applied():
    """Check if only the correct filters are applied."""
    try:
        filters = ipfs_api.get_swarm_filters()

        expected_filters = {
            f"/ip4/{cidr.network_address}/ipcidr/{cidr.prefixlen}"
            for cidr in get_complement_cidrs(whitelist, blacklist)
        }
        result = filters == expected_filters
        logger.info(f"Strict filters applied: {result}")
        return result
    except ipfs_api.ipfshttpclient.exceptions.ConnectionError as e:
        logger.error(f"ConnectionError: {e}")
        return False


#
# def notify(title, message):
#     logger.info(f"{title}: {message}")
#     result = subprocess.run(["notify-send", title, message])
#     if result.stderr:
#         logger.error(result.stderr)


gi.require_version("Notify", "0.7")

# Initialize notifications once
Notify.init("Ping Latency Monitor")


def notify(title, message):
    n = Notify.Notification.new(title, message)
    n.set_urgency(Notify.Urgency.NORMAL)
    n.show()


def get_ping_latency(PING_IP_ADDRESS, timeout):
    """"""
    ping_process = subprocess.Popen(
        ["ping", "-U", "-c", "1", "-W", str(timeout), PING_IP_ADDRESS],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, _ = ping_process.communicate()

    if ping_process.returncode == 0:
        match = re.search(r"time=([\d.]+) ms", output.decode("utf-8"))
        if match:
            return float(match.group(1))


latencies = []
notified = False


def ping_once() -> float | None:
    try:
        output = subprocess.run(
            ["ping", "-c", "1", "-w", "2", PING_TARGET],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if output.returncode != 0:
            return None  # Network unreachable or timeout

        # Extract latency from output
        for line in output.stdout.splitlines():
            if "time=" in line:
                latency = float(line.split("time=")[1].split(" ")[0])
                return latency

    except Exception as e:
        return None

    return None


def do_latency_measurement() -> float | None:
    latency = ping_once()

    if latency is not None:
        latencies.append(latency)
        if len(latencies) > WINDOW_SIZE:
            latencies.pop(0)

        avg_latency = statistics.mean(latencies)
        # print(avg_latency)
        return avg_latency
    else:
        # No connectivity, clear state
        latencies.clear()
        return None


def check_pings():
    """
    Gather network metrics, limit or unlimit IPFS accordingly, log results."""
    global notified
    peers_count = get_num_ipfs_peers()
    limitation = are_strict_filters_applied()

    avg_latency = do_latency_measurement()
    if peers_count > MAX_PEERS_COUNT and not limitation:
        apply_strict_filters()

    if limitation:
        if (
            avg_latency
            and avg_latency < PING_UNLIMIT_THRESHOLD_MS
            and peers_count < MAX_PEERS_COUNT
        ):
            remove_strict_filters()
    else:
        if avg_latency and avg_latency > PING_LIMIT_THRESHOLD_MS:
            apply_strict_filters()

    if avg_latency and avg_latency > PING_NOTIFY_THRESHOLD_MS:
        if not notified:
            notify(
                "⚠️ High Ping Latency ⚠️",
                f"Average ping to {PING_TARGET} is {int(avg_latency)}ms (>{
                    PING_NOTIFY_THRESHOLD_MS
                }ms)",
            )
            notified = True
    else:
        notified = False  # Reset so we can notify again if needed
    logger.info(f"{avg_latency},{peers_count},{int(limitation)}")


def get_num_ipfs_peers():
    """Get the number of peers this IPFS node is connected to."""
    try:
        return len(list(dict(ipfs_api.http_client.swarm.peers())["Peers"]))
    except Exception:
        return 0


# Set up log rotation with retention
logger.remove(0)  # remove default logger
# add custom logger for printing to console
logger.add(sys.stdout, format="<level>{message}</level>")
# add logger for writing to log file
logger.add(
    LOG_FILE_PATH,
    format="{time:DD-MMM-YYYY HH:mm:ss},{message}",
    rotation="1 MB",
    retention="5 days",
)


def run_monitor():
    remove_strict_filters()
    while True:
        try:
            check_pings()
        except ipfs_api.ipfshttpclient.exceptions.ConnectionError as e:
            logger.error(f"ConnectionError: {e}")
        sleep(1)


if __name__ == "__main__":
    run_monitor()
