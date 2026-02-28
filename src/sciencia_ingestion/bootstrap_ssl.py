import truststore

def inject_truststore() -> None:
    # Never disable SSL verification. Use OS trust store.
    truststore.inject_into_ssl()
