# Storage Server

Storage server for Poste Restante.

// TODO: Update this README with more details about the storage server, its endpoints, and usage instructions.

## Usage (temp dev)

```shell
docker run -d \
  --name poste-restante-mongo \
  -p 27017:27017 \
  mongo:7
````
or if it exists already, run:
```shell
docker start poste-restante-mongo
```
then
```shell
fastapi dev src/main.py
```