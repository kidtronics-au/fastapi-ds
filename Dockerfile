FROM postgres:16-bookworm AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-16

RUN git clone https://github.com/pgvector/pgvector.git \
 && cd pgvector \
 && make

FROM postgres:16-bookworm

COPY --from=builder /pgvector/vector.so /usr/lib/postgresql/16/lib/
COPY --from=builder /pgvector/vector.control /usr/share/postgresql/16/extension/
COPY --from=builder /pgvector/sql/* /usr/share/postgresql/16/extension/