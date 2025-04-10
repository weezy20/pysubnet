# PySubnet

## Description
Automates the process of generating keys, inserting them into keystore for substrate based chains;
Also generates libp2p node keys and edits the chainspec file accordingly to include them.
Currently works only for `AURA`+`Grandpa` chains however it's not too difficult to modify the contents of this script to suit your own `key-type`

## Usage

### Pre-requisites
Make sure you've got your `chainspec.json`, and the substrate binary, called `substrate` in the script (change as per your need).

If using `AccountId20`s, requires [moonkey](https://github.com/PureStake/moonbeam/releases/download/v0.8.0/moonkey) in your $PATH

```shell
python main.py
```

It will complain if `ROOT_DIR` already exists and has contents inside it. So run 
```sh
python main.py clean
```
to delete `ROOT_DIR` and start afresh.

By default it uses `dev` chainspec. To provide your own chainspec pass in `--chainspec <your chainspec file>`

All generated keys and node details are stored under `ROOT_DIR/pysubnet.json`

You can also use interactive mode by passing in `i` or `interactive` as an extra flag:

```sh
python main.py i
```

## Run a private network:

```sh
python main.py run
```
