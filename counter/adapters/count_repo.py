from typing import List

from counter.domain.models import ObjectCount
from counter.domain.ports import ObjectCountRepo


class CountInMemoryRepo(ObjectCountRepo):

    def __init__(self):
        self.store = dict()

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        if object_classes is None:
            return list(self.store.values())

        return [self.store.get(object_class) for object_class in object_classes]

    def update_values(self, new_values: List[ObjectCount]):
        for new_object_count in new_values:
            key = new_object_count.object_class
            try:
                stored_object_count = self.store[key]
                self.store[key] = ObjectCount(key, stored_object_count.count + new_object_count.count)
            except KeyError:
                self.store[key] = ObjectCount(key, new_object_count.count)


class CountPostgresRepo(ObjectCountRepo):
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("A PostgreSQL DSN must be configured")
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "The PostgreSQL adapter requires psycopg; install the project requirements"
            ) from error
        self.__psycopg = psycopg
        self.__dsn = dsn
        with self.__psycopg.connect(self.__dsn) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS object_counts (
                    object_class TEXT PRIMARY KEY,
                    count BIGINT NOT NULL
                )
                """
            )

    def read_values(self, object_classes: List[str] = None) -> List[ObjectCount]:
        with self.__psycopg.connect(self.__dsn) as connection:
            if object_classes is None:
                rows = connection.execute(
                    "SELECT object_class, count FROM object_counts ORDER BY object_class"
                ).fetchall()
            elif not object_classes:
                return []
            else:
                rows = connection.execute(
                    """
                    SELECT object_class, count
                    FROM object_counts
                    WHERE object_class = ANY(%s)
                    ORDER BY object_class
                    """,
                    (object_classes,),
                ).fetchall()
        return [ObjectCount(object_class, count) for object_class, count in rows]

    def update_values(self, new_values: List[ObjectCount]):
        if not new_values:
            return
        with self.__psycopg.connect(self.__dsn) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO object_counts (object_class, count)
                    VALUES (%s, %s)
                    ON CONFLICT (object_class)
                    DO UPDATE SET count = object_counts.count + EXCLUDED.count
                    """,
                    [(value.object_class, value.count) for value in new_values],
                )

