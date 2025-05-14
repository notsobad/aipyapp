import os
import time
import webbrowser

import requests
import qrcode

from aipyapp.aipy.i18n import T

POLL_INTERVAL = 5 # 轮询间隔（秒）

class TrustTokenAPI:
    """Handles all HTTP operations for TrustToken binding and authentication."""
    
    def __init__(self, coordinator_url=None):
        """
        Initialize the TrustToken API handler.
        
        Args:
            coordinator_url (str, optional): The coordinator server URL. Defaults to None.
        """
        self.coordinator_url = coordinator_url or T('tt_coordinator_url')

    def request_binding(self):
        """Request binding from the coordinator server.
        
        Returns:
            dict: Response data containing approval_url, request_id, and expires_in if successful
            None: If the request failed
        """
        url = f"{self.coordinator_url}/request_bind"
        try:
            response = requests.post(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(T('coordinator_request_error').format(e))
            return None
        except Exception as e:
            print(T('unexpected_request_error').format(e))
            return None

    def check_status(self, request_id):
        """Check the binding status from the coordinator server.
        
        Args:
            request_id (str): The request ID to check status for.
            
        Returns:
            dict: Response data containing status and secret_token if approved
            None: If the request failed
        """
        url = f"{self.coordinator_url}/check_status"
        params = {'request_id': request_id}
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(T('coordinator_polling_error').format(e))
            return None
        except Exception as e:
            print(T('unexpected_polling_error').format(e))
            return None

class TrustToken:
    """A class to handle TrustToken binding and authentication processes."""
    
    def __init__(self, coordinator_url=None, poll_interval=5):
        """
        Initialize the TrustToken handler.
        
        Args:
            coordinator_url (str, optional): The coordinator server URL. Defaults to None.
            poll_interval (int, optional): Polling interval in seconds. Defaults to 5.
        """
        self.api = TrustTokenAPI(coordinator_url)
        self.poll_interval = poll_interval or POLL_INTERVAL

    def request_binding(self, qrcode=False):
        """Request binding from the coordinator server.
        
        Returns:
            str: The request ID if successful, None otherwise.
        """
        data = self.api.request_binding()
        if not data:
            return None

        approval_url = data['approval_url']
        request_id = data['request_id']
        expires_in = data['expires_in']

        print(T('binding_request_sent').format(request_id, approval_url, expires_in))
        if qrcode:
            print(T('scan_qr_code'))
            try:
                qr = qrcode.QRCode(
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    border=1
                )
                qr.add_data(approval_url)
                qr.make(fit=True)
                qr.print_ascii(tty=True)
                print(T('config_help'))
            except Exception as e:
                print(T('qr_code_display_failed').format(e))
        else:
            webbrowser.open(approval_url)
        return request_id

    def poll_status(self, request_id, save_func=None):
        """Poll the binding status from the coordinator server.
        
        Args:
            request_id (str): The request ID to check status for.
            save_func (callable, optional): Function to save the token when approved.
            
        Returns:
            bool: True if binding was successful, False otherwise.
        """
        start_time = time.time()
        polling_timeout = 310

        print(T('waiting_for_approval'), end='', flush=True)
        try:
            while time.time() - start_time < polling_timeout:
                data = self.api.check_status(request_id)
                if not data:
                    time.sleep(self.poll_interval)
                    continue

                status = data.get('status')
                if status == 'pending':
                    print('.', end='', flush=True)
                    time.sleep(self.poll_interval)
                    continue

                print()
                print(T('current_status').format(status))

                if status == 'approved':
                    if save_func:
                        save_func(data['secret_token'])
                    return True
                elif status == 'expired':
                    print(T('binding_expired'))
                    return False
                else:
                    print(T('unknown_status').format(status))
                    return False

                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print(T('polling_cancelled'))
            return False

        print(T('polling_timeout'))
        return False

    def fetch_token(self, save_func):
        """Fetch a token from the coordinator server.
        
        Args:
            save_func (callable): Function to save the token when approved.
            
        Returns:
            bool: True if token was successfully fetched and saved, False otherwise.
        """
        print(T('start_binding_process'))
        req_id = self.request_binding()
        if req_id:
            if self.poll_status(req_id, save_func):
                print(T('binding_success'))
                return True
            else:
                print(T('binding_failed'))
                return False
        else:
            print(T('binding_request_failed'))
            return False

if __name__ == "__main__":
    tt = TrustToken()
    tt.fetch_token(lambda token: print(f"Token: {token}"))