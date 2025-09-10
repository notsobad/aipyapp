#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from aipyapp import TaskPlugin

class WebToolsPlugin(TaskPlugin):
    """Web Tools - Provides web page scraping, URL analysis, and HTTP request capabilities."""
    
    name = "web_tools"
    version = "1.0.0"
    description = "Web Tools - Provides web page scraping, URL analysis, and HTTP request capabilities."
    author = "AiPy Team"
    
    def init(self):
        """Initialize network tool configuration."""
        self.timeout = self.config.get('timeout', 30)
        self.user_agent = self.config.get('user_agent', 'AiPy WebTools/1.0')
        self.max_content_length = self.config.get('max_content_length', 1024 * 1024)  # 1MB
        self.headers = {
            'User-Agent': self.user_agent,
            **self.config.get('default_headers', {})
        }
        
        self.logger.info(f"Initialized network tool, timeout: {self.timeout}s")
    
    def fn_fetch_webpage(self, url: str, extract_text: bool = True) -> Dict[str, Any]:
        """
        Fetch webpage content.
        
        Args:
            url: Target URL.
            extract_text: Whether to extract only text content.
            
        Returns:
            Dictionary containing webpage information.
        
        Examples:
            >>> fn_fetch_webpage("https://www.baidu.com")
            {'success': True, 'url': 'https://www.baidu.com', 'status_code': 200, 'headers': {'Content-Type': 'text/html; charset=utf-8'}, 'content_type': 'text/html; charset=utf-8', 'encoding': 'utf-8', 'text': 'Baidu', 'title': 'Baidu'}
            >>> fn_fetch_webpage("https://www.baidu.com", extract_text=False)
            {'success': True, 'url': 'https://www.baidu.com', 'status_code': 200, 'headers': {'Content-Type': 'text/html; charset=utf-8'}, 'content_type': 'text/html; charset=utf-8', 'encoding': 'utf-8', 'content': '<!DOCTYPE html>...'}    
        """
        return self._fetch_webpage(url, extract_text)
    
    def fn_http_request(self, url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send HTTP request.
        
        Args:
            url: Request URL.
            method: HTTP method (GET/POST/PUT/DELETE, etc.).
            headers: Request headers.
            params: URL parameters.
            json_data: JSON request body.
                
        Returns:
            Dictionary containing webpage information, where content is the response content, success is whether it is successful, and status_code is the status code.

        Examples:
            >>> fn_http_request("https://www.baidu.com")
            {'success': True, 'status_code': 200, 'headers': {'Content-Type': 'text/html; charset=utf-8'}, 'content': 'Baidu', 'elapsed': '0.000000s'}
            >>> fn_http_request("https://www.baidu.com", method="POST", json_data={"name": "John", "age": 30})
            {'success': True, 'status_code': 200, 'headers': {'Content-Type': 'text/html; charset=utf-8'}, 'content': 'Baidu', 'elapsed': '0.000000s'}
            >>> fn_http_request("https://www.baidu.com")
            {'sucess': False, 'error': '400 Client Error: Bad Request for url'}
        """
        return self._http_request(url, method, headers, params, json_data)
        
    def fn_analyze_url(self, url: str) -> Dict[str, str]:
        """
        Analyze the various components of the URL.
        
        Args:
            url: URL to be analyzed.
            
        Returns:
            Dictionary containing URL component information.
        """
        return self._analyze_url(url)
    
    def fn_check_url_status(self, url: str) -> Dict[str, Any]:
        """
        Check URL status.
        
        Args:
            url: Target URL.
            
        Returns:
            Dictionary containing URL status information.
        """
        return self._check_url_status(url)
    
    def _fetch_webpage(self, url: str, extract_text: bool) -> Dict[str, Any]:
        """Fetch webpage content."""
        try:
            response = requests.get(
                url, 
                headers=self.headers,
                timeout=self.timeout,
                stream=True
            )
            
            # Check content length.
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_content_length:
                return {
                    "success": False,
                    "error": f"Content too large ({content_length} bytes), exceeds limit ({self.max_content_length} bytes)"
                }
            
            response.raise_for_status()
            
            result = {
                "success": True,
                "url": url,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get('content-type', ''),
                "encoding": response.encoding
            }
            
            if extract_text and 'text/html' in response.headers.get('content-type', ''):
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Remove script and style tags.
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    result["text"] = soup.get_text(separator=' ', strip=True)
                    result["title"] = soup.title.string if soup.title else ""
                    
                except ImportError:
                    result["text"] = response.text
                    result["raw_html"] = response.text[:2000] + "..." if len(response.text) > 2000 else response.text
            else:
                result["content"] = response.text[:2000] + "..." if len(response.text) > 2000 else response.text
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch webpage {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
    
    def _analyze_url(self, url: str) -> Dict[str, str]:
        """Analyze URL structure."""
        try:
            parsed = urlparse(url)
            return {
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "hostname": parsed.hostname,
                "port": str(parsed.port) if parsed.port else "",
                "path": parsed.path,
                "params": parsed.params,
                "query": parsed.query,
                "fragment": parsed.fragment,
                "username": parsed.username or "",
                "password": "***" if parsed.password else ""
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _http_request(self, url: str, method: str, headers: Optional[Dict], params: Optional[Dict], json_data: Optional[Dict]) -> Dict[str, Any]:
        """Send HTTP request."""
        try:
            request_headers = self.headers.copy()
            if headers:
                request_headers.update(headers)
            
            kwargs = {
                'headers': request_headers,
                'timeout': self.timeout,
                'params': params
            }
            
            if json_data:
                kwargs['json'] = json_data
            
            response = requests.request(method.upper(), url, **kwargs)
            
            return {
                "success": True,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text,
                "elapsed": str(response.elapsed)
            }
            
        except Exception as e:
            self.logger.error(f"HTTP request failed {method} {url}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _check_url_status(self, url: str) -> Dict[str, Any]:
        """Check URL status."""
        try:
            response = requests.head(url, headers=self.headers, timeout=self.timeout)
            return {
                "accessible": True,
                "status_code": response.status_code,
                "content_type": response.headers.get('content-type', ''),
                "content_length": response.headers.get('content-length', ''),
                "last_modified": response.headers.get('last-modified', ''),
                "server": response.headers.get('server', '')
            }
        except Exception as e:
            return {
                "accessible": False,
                "error": str(e)
            }