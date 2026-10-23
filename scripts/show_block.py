"""Show a forbidden operation, then STOP blocking an allowlisted operation."""
import argparse
import requests


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator',required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8787', choices=['http://127.0.0.1:8787'])
    args=parser.parse_args(argv)
    with requests.Session() as client:
        response=client.post(args.base_url+'/actions/execute',json={'action':'delete_database','target':'payment',
            'parameters':{},'report':{},'idempotency_key':'forbidden-demo'}, timeout=10)
        print(response.status_code,response.json())
        if response.status_code != 403 or response.json().get('reason_codes') != ['FORBIDDEN_OPERATION']:
            raise RuntimeError('The forbidden action was not blocked as expected')
        response=client.post(args.base_url+'/stop',json={'operator':args.operator}, timeout=10)
        response.raise_for_status()
        print(response.json())
        response=client.post(args.base_url+'/actions/dry-run',json={'action':'restart_service','target':'recommendation',
            'parameters':{'service':'recommendation'},'report':{}}, timeout=10)
        print(response.status_code,response.json())
        if response.status_code != 423 or response.json().get('reason_codes') != ['STOP_LATCHED']:
            raise RuntimeError('STOP did not block the allowed operation as expected')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
