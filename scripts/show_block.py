"""Demonstrate the HTTP forbidden-operation response, then latch STOP."""
import argparse
from fastapi.testclient import TestClient
from action_api.app import create_app


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator',required=True)
    args=parser.parse_args(argv)
    with TestClient(create_app()) as client:
        response=client.post('/actions/execute',json={'action':'delete_database','target':'payment',
            'parameters':{},'report':{},'idempotency_key':'forbidden-demo'})
        print(response.status_code,response.json())
        if response.status_code != 403 or response.json().get('reason_codes') != ['FORBIDDEN_OPERATION']:
            raise RuntimeError('The forbidden action was not blocked as expected')
        response=client.post('/stop',json={'operator':args.operator})
        response.raise_for_status()
        print(response.json())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
