# IPFS Throttler

A system for monitoring and limiting IPFS' effect on LAN performance.

This project consists of a python script that monitors network latency with pings and limits the running IPFS node's ability to connect to new peers when the latency surpasses a specified threshold, to avoid the IPFS node from seriously harming the network's internet connectivity.

## Background

IPFS, the InterPlanetary FileSystem, is a great piece of infrastructure for peer-to-peer communications.
In my experience, the main disadvantage it has is that it causes some home routers to overload or crash in different ways.
This issue has so far been tracked in the following Github issue pages:

- https://github.com/ipfs/kubo/issues/3311
- https://github.com/ipfs/kubo/issues/3320
- https://github.com/ipfs/kubo/issues/9998

In my experience, the problem seems to correlate with the number of IPFS peers the concerned node is connected to.
The only effective way I have found so far for limited the number of nodes a peer is connected to is to disable the creation of new IPv4 connections by running the following command:

```sh
ipfs swarm filters add /ip4/0.0.0.0/ipcidr/0
```

Since keeping this configuration active seriously reduces IPFS connectivity, I created this project to automate its activation when the network performance shows signs of overloading, and deactivating it when the performance has reached its baseline again.
Network performance is measured in latency via the average ping times to `/ip4/8.8.8.8`.

I encourage you to adapt this script for other network metrics and IPFS limitation measures you find useful and share your findings to help the community solve this issue which IPFS has.

## Function

This script performs the following loop:

- gather network metrics
- decide whether to apply or remove limitations on IPFS
- log timestamp, network metrics, number of IPFS peers and state of IPFS limitations to a CSV file

### Configuration

Below are the current configurations for the gathered network metrics, the decision logic for applying or removing limitations on IPFS, and what those limitations entail.
I encourage you to adapt this script for other network metrics and IPFS limitation measures you find useful and share your findings to help the community solve this issue which IPFS has.

#### Used Network Metrics

- run a certain number of pings (`PING_SAMPLE_COUNT` times) and calculate their average
  -> however, if a ping times out (after `PING_COMMAND_TIMEOUT_S` seconds), abort the ping sampling immediately

#### Application/Removal of Limitations

- if a ping timed out, apply limitations
- if the average latency was greater than `PING_LIMIT_THRESHOLD_MS` milliseconds, apply limitations
- if the average latency was less than `PING_UNLIMIT_THRESHOLD_MS` milliseconds, remove limitations

#### Limitations

- a swarm filter of `/ip4/0.0.0.0/ipcidr/0`, effectively disabling the creation of new IPv4 connections

## Running from Source

Download this project, install the prerequisites listed in `requirements.txt` and run the folder with Python.

```sh
git clone https://github.com/emendir/IPFS-Throttler
pip install -r ipfs-throttler/requirements.txt
python3 ipfs-throttler
```

### Requirements

- python3
- pip for python3
- virtualenv for python3

#### Debian:

On Debian you can install the requirements like this:

```sh
sudo apt install python3-virtualenv python3-pip git
```

## Installation

I've written an installer for Linux systems that use Systemd.
Read it first to make sure you're happy with what it does.

```sh

git clone https://github.com/emendir/IPFS-Throttler
./ipfs-throttler/install.sh
```

Logs are written to `/opt/ipfs_throttler/IPFS_Ping_Monitor.csv`

## Contributing

### Get Involved

- GitHub Discussions: if you want to share ideas
- GitHub Issues: if you find bugs, other issues, or would like to submit feature requests
- GitHub Merge Requests: if you think you know what you're doing, you're very welcome!

### Donations

To support me in my work on this and other projects, you can make donations with the following currencies:

- **Bitcoin:** `BC1Q45QEE6YTNGRC5TSZ42ZL3MWV8798ZEF70H2DG0`
- **Ethereum:** `0xA32C3bBC2106C986317f202B3aa8eBc3063323D4`
- [**Fiat** (via Credit or Debit Card, Apple Pay, Google Pay, Revolut Pay)](https://checkout.revolut.com/pay/4e4d24de-26cf-4e7d-9e84-ede89ec67f32)

Donations help me:
- dedicate more time to developing and maintaining open-source projects
- cover costs for IT infrastructure
- finance projects requiring additional hardware & compute

## About the Developer

This project is developed by a human one-man team, publishing under the name _Emendir_.  
I build open technologies trying to improve our world;
learning, working and sharing under the principle:

> _Freely I have received, freely I give._

Feel welcome to join in with code contributions, discussions, ideas and more!

## Open-Source in the Public Domain

I dedicate this project to the public domain.
It is open source and free to use, share, modify, and build upon without restrictions or conditions.

I make no patent or trademark claims over this project.  

Formally, you may use this project under either the: 
- [MIT No Attribution (MIT-0)](https://choosealicense.com/licenses/mit-0/) or
- [Creative Commons Zero (CC0)](https://choosealicense.com/licenses/cc0-1.0/)
licence at your choice.  


