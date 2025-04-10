# PySubnet

## Description
Automates the process of generating keys, inserting them into keystore for substrate based chains
Currently works only for `AURA`+`Grandpa` chains however it's not too difficult to modify the contents of this script to suit your own `key-type`

## Usage
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