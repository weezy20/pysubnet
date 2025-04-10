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