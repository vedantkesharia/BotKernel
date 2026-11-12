import os
import time
import signal
import logging

running = True
def stop(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from sqlalchemy import text
from botkernel.core import engine, execute, sweep
from botkernel.observability import (
    capture_trace_context,
    extract_trace_context,
    operation,
    trace_context_from_kafka,
    traced_span,
)
from prometheus_client import start_http_server
from opentelemetry.trace import Link, SpanKind
from uuid import UUID
from sqlalchemy.exc import NoResultFound

broker = os.getenv("KAFKA_BOOTSTRAP_SERVERS","kafka:9092")
def publish():
    p = Producer({"bootstrap.servers":broker,"enable.idempotence":True})
    while running:
        with traced_span("botkernel.outbox.poll") as poll_span:
            with engine.begin() as c:
                rows = c.execute(text("SELECT * FROM outbox WHERE NOT published ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 100")).mappings().all()
                for row in rows:
                    action_id = str(row["action_id"])
                    parent_context = extract_trace_context(row["trace_context"] or {})
                    with traced_span(
                        "botkernel.outbox.load",
                        {"action.id": action_id},
                        parent_context=parent_context,
                        links=[Link(poll_span.get_span_context())],
                    ):
                        errors = []
                        topic = os.getenv("KAFKA_TOPIC","actions")
                        with traced_span(
                            "botkernel.kafka.publish",
                            {
                                "action.id": action_id,
                                "messaging.destination": topic,
                            },
                            kind=SpanKind.PRODUCER,
                        ) as span:
                            headers = [
                                (key, value.encode("ascii"))
                                for key, value in (capture_trace_context() or {}).items()
                            ]
                            p.produce(
                                topic,
                                key=action_id,
                                value=action_id,
                                headers=headers,
                                on_delivery=lambda err, msg: errors.append(err) if err else None,
                            )
                            with operation("publication"):
                                if p.flush(10) or errors:
                                    span.set_attribute("botkernel.outcome", "failed")
                                    raise RuntimeError("Kafka publication failed; outbox retained")
                            span.set_attribute("botkernel.outcome", "published")
                            logging.info(
                                "Kafka acknowledged action event",
                                extra={
                                    "event": "kafka_event_published",
                                    "action_id": action_id,
                                    "messaging_destination": topic,
                                    "botkernel_outcome": "broker_acknowledged",
                                },
                            )
                        if os.getenv("CRASH_AFTER_PUBLISH") == "true":
                            os._exit(18)
                        c.execute(text("UPDATE outbox SET published=true WHERE id=:id"), {"id":row["id"]})
        time.sleep(.2)

def consume():
    c = Consumer({"bootstrap.servers":broker,"group.id":"executors","auto.offset.reset":"earliest","enable.auto.commit":False,"session.timeout.ms":6000,"heartbeat.interval.ms":2000})
    c.subscribe([os.getenv("KAFKA_TOPIC","actions")])
    try:
        while running:
            msg = c.poll(1)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() in (KafkaError.UNKNOWN_TOPIC_OR_PART, KafkaError._UNKNOWN_TOPIC):
                    time.sleep(1)
                    continue
                raise KafkaException(msg.error())
            parent_context = trace_context_from_kafka(msg.headers())
            with traced_span(
                "botkernel.kafka.consume",
                {
                    "messaging.destination": msg.topic(),
                    "messaging.kafka.partition": msg.partition(),
                    "messaging.kafka.offset": msg.offset(),
                },
                parent_context=parent_context,
                kind=SpanKind.CONSUMER,
            ) as span:
                action_id = None
                try:
                    action_id = str(UUID((msg.value() or b"").decode()))
                    span.set_attribute("action.id", action_id)
                    with operation("delivery"):
                        execute(action_id)
                    span.set_attribute("botkernel.outcome", "processed")
                    if os.getenv("CRASH_AFTER_COMPLETION") == "true":
                        os._exit(19)
                except (ValueError, UnicodeError, NoResultFound):
                    with engine.begin() as db:
                        db.execute(text("INSERT INTO dead_letters VALUES (:t,:p,:o,'invalid or unknown action') ON CONFLICT DO NOTHING"), {'t':msg.topic(),'p':msg.partition(),'o':msg.offset()})
                    span.set_attribute("botkernel.outcome", "dead_lettered")
                logging.info(
                    "Kafka event handled",
                    extra={
                        "event": "kafka_event_handled",
                        "action_id": action_id,
                        "messaging_destination": msg.topic(),
                        "messaging_kafka_partition": msg.partition(),
                        "messaging_kafka_offset": msg.offset(),
                        "botkernel_outcome": "processed" if action_id else "dead_lettered",
                    },
                )
                c.commit(message=msg,asynchronous=False)
    finally:
        c.close()

if __name__ == "__main__":
    from botkernel.observability import configure_logging, configure_telemetry
    configure_telemetry(os.getenv("OTEL_SERVICE_NAME", "botkernel-worker"))
    configure_logging(os.getenv("OTEL_SERVICE_NAME", "botkernel-worker"))
    if os.getenv("METRICS_ENABLED") == "true":
        try:
            start_http_server(9100)
        except OSError:
            logging.warning("Metrics listener unavailable; execution continues")
    if os.getenv("ROLE") == "controller":
        from botkernel.stability import tick
        while running:
            with operation("controller"):
                tick()
            time.sleep(1)
    elif os.getenv("ROLE") == "recovery":
        while running:
            with operation("recovery_sweep"):
                attempted = sweep()
            if attempted:
                logging.info(
                    "Recovery sweep processed due actions",
                    extra={"event": "recovery_sweep_completed", "botkernel_outcome": "attempted"},
                )
            time.sleep(1)
    else:
        publish() if os.getenv("ROLE") == "publisher" else consume()
