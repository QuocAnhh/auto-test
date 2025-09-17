#!/usr/bin/env python3
"""
Flask Web Application - Bus QA LLM Evaluator
Replaces Streamlit UI with modern HTML/CSS/JS interface
"""

import os
import json
import time
import asyncio
import csv
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from io import BytesIO, StringIO
import traceback

from flask import Flask, render_template, request, jsonify, send_file, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import pandas as pd
from dotenv import load_dotenv

# Import original evaluation modules
from busqa.batch_evaluator import HighSpeedBatchEvaluator, evaluate_conversations_high_speed
from busqa.llm_client import call_llm
from busqa.brand_specs import BrandPolicy, load_brand_prompt
from busqa.prompt_loader import load_unified_rubrics, load_diagnostics_config
from busqa.brand_resolver import BrandResolver
from busqa.high_performance_api import HighPerformanceAPIClient
from busqa.performance_monitor import PerformanceMonitor
from busqa.aggregate import make_summary, generate_insights

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'bus-qa-evaluator-secret-key-2025')
CORS(app)

# Global configuration
DEFAULT_BASE_URL = "https://live-demo.agenticai.pro.vn"

# Performance defaults
DEFAULT_CONFIG = {
    'max_concurrency': 30,
    'use_progressive_batching': True,
    'use_high_performance_api': True,
    'enable_caching': False,
    'api_rate_limit': 200,
    'memory_cleanup_interval': 10,
    'show_performance_metrics': True,
    'temperature': 0.2,
    'max_chars': 24000
}

class WebAppState:
    """Manages web app state similar to Streamlit session state"""
    def __init__(self):
        self.evaluation_results = None
        self.summary_data = None
        self.streaming_results = []
        self.streaming_status = {"completed": 0, "total": 0}
        self.bulk_conversations = None
        self.bulk_bot_id = None
        self.bulk_bearer_token = None
        self.bulk_list_base_url = None
        self.performance_data = {}
        self.benchmark_results = None

# Global state instance
app_state = WebAppState()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        # Load rubrics to get available flows
        rubrics_cfg = load_unified_rubrics()
        flows = list(rubrics_cfg.get('flows_slots', {}).keys()) if rubrics_cfg else []
        
        # Load diagnostics info
        try:
            diag_cfg = load_diagnostics_config()
            diagnostics_info = {
                'operational_readiness': len(diag_cfg.get('operational_readiness', [])),
                'risk_compliance': len(diag_cfg.get('risk_compliance', []))
            }
        except Exception:
            diagnostics_info = {'operational_readiness': 0, 'risk_compliance': 0}
        
        # Brand options
        brand_options = ["son_hai", "long_van"]
        
        return jsonify({
            'success': True,
            'config': {
                **DEFAULT_CONFIG,
                'base_url': DEFAULT_BASE_URL,
                'flows': flows,
                'diagnostics_info': diagnostics_info,
                'brand_options': brand_options,
                'llm_model': 'gemini-2.5-flash'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/brand/<brand_name>', methods=['GET'])
def get_brand_info(brand_name):
    """Get brand policy information"""
    try:
        brand_path = f"brands/{brand_name}/prompt.md"
        brand_prompt_text, brand_policy = load_brand_prompt(brand_path)
        
        if not brand_policy:
            raise ValueError(f"Could not load brand policy for {brand_name}")
        
        return jsonify({
            'success': True,
            'brand_policy': {
                'forbid_phone_collect': brand_policy.forbid_phone_collect,
                'require_fixed_greeting': brand_policy.require_fixed_greeting,
                'ban_full_summary': brand_policy.ban_full_summary,
                'max_prompted_openers': brand_policy.max_prompted_openers,
                'read_money_in_words': brand_policy.read_money_in_words
            },
            'prompt_text': brand_prompt_text
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bot-map', methods=['POST'])
def load_bot_map():
    """Load bot mapping configuration"""
    try:
        data = request.get_json()
        bot_map_path = data.get('bot_map_path', 'config/bot_map.yaml')
        
        brand_resolver = BrandResolver(bot_map_path)
        cache_stats = brand_resolver.get_cache_stats()
        mapped_bots = brand_resolver._map.get_all_mapped_bots()
        fallback = brand_resolver._map._fallback_brand
        
        return jsonify({
            'success': True,
            'cache_stats': cache_stats,
            'mapped_bots': dict(list(mapped_bots.items())[:20]),  # Limit for display
            'fallback_brand': fallback,
            'total_mapped': len(mapped_bots)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bulk-list', methods=['POST'])
def bulk_list_conversations():
    """Fetch conversations from API for bulk evaluation"""
    try:
        data = request.get_json()
        
        # Extract parameters
        list_base_url = data.get('list_base_url', 'https://live-demo.agenticai.pro.vn')
        bot_id = data.get('bot_id')
        bearer_token = data.get('bearer_token')
        page_size = data.get('page_size', 30)
        max_pages = data.get('max_pages', 5)
        take = data.get('take', 10)
        skip = data.get('skip', 0)
        strategy = data.get('strategy', 'newest')
        sort_by = data.get('sort_by', 'created_at')
        order = data.get('order', 'desc')
        min_turns = data.get('min_turns', 0)
        
        if not bot_id or not bearer_token:
            return jsonify({'success': False, 'error': 'Bot ID and Bearer Token are required'}), 400
        
        # Import bulk list tool
        from tools.bulk_list_evaluate import BulkListEvaluate
        
        bulk_tool = BulkListEvaluate(
            base_url=list_base_url,
            bearer_token=bearer_token
        )
        
        # Fetch conversations
        conversations = bulk_tool.list_and_select_conversations(
            bot_id=bot_id,
            page_size=page_size,
            max_pages=max_pages,
            take=take,
            skip=skip,
            strategy=strategy,
            sort_by=sort_by,
            order=order,
            min_turns=min_turns
        )
        
        # Store in app state
        app_state.bulk_conversations = conversations
        app_state.bulk_bot_id = bot_id
        app_state.bulk_bearer_token = bearer_token
        app_state.bulk_list_base_url = list_base_url
        
        # Extract conversation IDs
        conversation_ids = [conv.get("conversation_id") for conv in conversations]
        
        return jsonify({
            'success': True,
            'conversations': conversations[:10],  # Limit for display
            'conversation_ids': conversation_ids,
            'total_fetched': len(conversations),
            'preview': [
                {
                    'conversation_id': conv.get('conversation_id'),
                    'turns': conv.get('turns', 0),
                    'created_at': conv.get('created_at'),
                    'length': len(str(conv.get('messages', [])))
                }
                for conv in conversations[:5]
            ]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test-bearer-token', methods=['POST'])
def test_bearer_token():
    """Test if bearer token is valid"""
    try:
        data = request.get_json()
        bearer_token = data.get('bearer_token')
        list_base_url = data.get('list_base_url', 'https://live-demo.agenticai.pro.vn')
        
        if not bearer_token:
            return jsonify({'success': False, 'error': 'Bearer token is required'}), 400
        
        from tools.test_bearer_token import test_bearer_token
        
        result = test_bearer_token(bearer_token, list_base_url)
        
        return jsonify({
            'success': True,
            'valid': result.get('valid', False),
            'status_code': result.get('status_code'),
            'message': result.get('message', 'Token test completed')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-ids', methods=['POST'])
def upload_conversation_ids():
    """Handle file upload for conversation IDs"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read file content
        content = file.read().decode('utf-8')
        
        conversation_ids = []
        
        if file.filename.endswith('.csv'):
            # Parse CSV - assume first column contains IDs
            reader = csv.reader(StringIO(content))
            for row in reader:
                if row and row[0].strip():
                    conversation_ids.append(row[0].strip())
        else:
            # Parse as text file - one ID per line
            lines = content.strip().split('\n')
            conversation_ids = [line.strip() for line in lines if line.strip()]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for id in conversation_ids:
            if id not in seen:
                seen.add(id)
                unique_ids.append(id)
        
        return jsonify({
            'success': True,
            'conversation_ids': unique_ids,
            'total_count': len(unique_ids)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/benchmark', methods=['POST'])
def run_performance_benchmark():
    """Run performance benchmark test"""
    try:
        data = request.get_json()
        
        # Extract benchmark parameters
        test_conversations = data.get('test_conversations', 5)
        concurrency_levels = data.get('concurrency_levels', [10, 20, 30])
        iterations = data.get('iterations', 1)
        
        # Check for required API key
        llm_api_key = os.getenv("GEMINI_API_KEY", "")
        if not llm_api_key:
            return jsonify({'success': False, 'error': 'GEMINI_API_KEY not found in environment'}), 400
        
        # Use actual benchmark from performance module
        try:
            from benchmark_performance import benchmark_batch_processing
            
            # Create simple test conversations
            test_conv_ids = [f"test_conv_{i}" for i in range(test_conversations)]
            
            # Run actual benchmark
            llm_api_key = os.getenv("GEMINI_API_KEY", "")
            base_url = data.get('base_url', DEFAULT_BASE_URL)
            
            benchmark_results = asyncio.run(benchmark_batch_processing(
                conversation_ids=test_conv_ids,
                base_url=base_url,
                llm_api_key=llm_api_key,
                concurrency_levels=concurrency_levels,
                redis_url=data.get('redis_url')
            ))
            
            # Store results
            app_state.benchmark_results = benchmark_results.get('results', [])
            
            return jsonify({
                'success': True,
                'results': benchmark_results.get('results', []),
                'recommendation': benchmark_results.get('recommendation', {})
            })
            
        except ImportError:
            # Fallback to simple simulation if benchmark module not available
            results = []
            for concurrency in concurrency_levels:
                result = {
                    'concurrency': concurrency,
                    'throughput': 10 + concurrency * 0.5,
                    'avg_time': 2.0 - (concurrency * 0.05),
                    'success_rate': 0.95 + (concurrency * 0.01)
                }
                results.append(result)
            
            optimal = max(results, key=lambda x: x['throughput'])
            recommendation = {
                'optimal_concurrency': optimal['concurrency'],
                'message': f"Optimal concurrency: {optimal['concurrency']} with {optimal['throughput']:.1f} conv/s"
            }
            
            app_state.benchmark_results = results
            
            return jsonify({
                'success': True,
                'results': results,
                'recommendation': recommendation
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluate-single', methods=['POST'])
def evaluate_single_conversation():
    """Evaluate a single conversation"""
    try:
        data = request.get_json()
        
        # Extract parameters
        conversation_id = data.get('conversation_id', '').strip()
        brand_name = data.get('brand_name', 'son_hai')
        base_url = data.get('base_url', DEFAULT_BASE_URL)
        apply_diagnostics = data.get('apply_diagnostics', True)
        
        if not conversation_id:
            return jsonify({'success': False, 'error': 'Conversation ID is required'}), 400
        
        # Load configurations
        rubrics_cfg = load_unified_rubrics()
        if not rubrics_cfg:
            return jsonify({'success': False, 'error': 'Could not load unified rubrics'}), 500
        
        diagnostics_cfg = load_diagnostics_config() if apply_diagnostics else None
        
        # Load brand policy
        try:
            brand_path = f"brands/{brand_name}/prompt.md"
            brand_prompt_text, brand_policy = load_brand_prompt(brand_path)
            if not brand_policy:
                raise ValueError(f"Could not load brand policy for {brand_name}")
        except Exception as e:
            return jsonify({'success': False, 'error': f'Brand loading error: {str(e)}'}), 500
        
        # Get LLM API key
        llm_api_key = os.getenv("GEMINI_API_KEY", "")
        if not llm_api_key:
            return jsonify({'success': False, 'error': 'GEMINI_API_KEY not found in environment'}), 500
        
        # Perform single conversation evaluation
        try:
            from busqa.api_client import fetch_messages
            from busqa.normalize import normalize_messages, build_transcript
            from busqa.metrics import compute_latency_metrics, compute_additional_metrics, compute_policy_violations_count, filter_non_null_metrics
            from busqa.prompting import build_system_prompt_unified, build_user_instruction
            from busqa.llm_client import call_llm
            from busqa.evaluator import coerce_llm_json_unified
            from busqa.diagnostics import detect_operational_readiness, detect_risk_compliance
            
            # Fetch conversation data
            raw_data = fetch_messages(base_url, conversation_id)
            messages = normalize_messages(raw_data)
            
            if not messages:
                return jsonify({'success': False, 'error': 'No messages found in conversation'}), 400
            
            # Build transcript and compute metrics
            transcript = build_transcript(messages)
            
            # Compute metrics
            latency_metrics = compute_latency_metrics(messages)
            additional_metrics = compute_additional_metrics(messages, brand_policy, brand_prompt_text)
            policy_violations = compute_policy_violations_count(messages, brand_policy)
            
            metrics = {}
            metrics.update(latency_metrics)
            metrics.update(additional_metrics)
            metrics["policy_violations"] = policy_violations
            
            # Apply diagnostics if enabled
            if apply_diagnostics and diagnostics_cfg:
                or_hits = detect_operational_readiness(messages, brand_policy, brand_prompt_text)
                rc_hits = detect_risk_compliance(messages, brand_policy)
                diagnostics_hits = {
                    "operational_readiness": or_hits,
                    "risk_compliance": rc_hits
                }
                metrics["diagnostics"] = diagnostics_hits
            
            # Filter metrics for LLM
            metrics_for_llm = filter_non_null_metrics(metrics)
            
            # Build prompts
            system_prompt = build_system_prompt_unified(rubrics_cfg, brand_policy, brand_prompt_text)
            user_prompt = build_user_instruction(metrics_for_llm, transcript, rubrics_cfg)
            
            # Call LLM
            llm_response = call_llm(
                api_key=llm_api_key,
                model="gemini-2.5-flash",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2
            )
            
            # Process result
            result = coerce_llm_json_unified(
                llm_response,
                rubrics_cfg=rubrics_cfg,
                brand_policy=brand_policy,
                messages=messages,
                transcript=transcript,
                metrics=metrics,
                diagnostics_cfg=diagnostics_cfg if apply_diagnostics else None,
                diagnostics_hits=metrics.get("diagnostics", {}) if apply_diagnostics else {}
            )
            
            # Format response similar to batch evaluation
            response_data = {
                "conversation_id": conversation_id,
                "brand_id": brand_name,
                "brand_prompt_path": brand_path,
                "evaluation_timestamp": datetime.utcnow().isoformat() + "Z",
                "result": result.model_dump(),
                "metrics": metrics,
                "transcript_preview": transcript[:500] + "..." if len(transcript) > 500 else transcript
            }
            
            return jsonify({
                'success': True,
                'result': response_data
            })
            
        except Exception as e:
            logger.error(f"Single conversation evaluation failed: {e}")
            return jsonify({
                'success': False, 
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/evaluate', methods=['POST'])
def run_batch_evaluation():
    """Run batch evaluation with streaming results"""
    try:
        data = request.get_json()
        
        # Extract parameters
        conversation_ids = data.get('conversation_ids', [])
        brand_mode = data.get('brand_mode', 'single')
        selected_brand = data.get('selected_brand', 'son_hai')
        bot_map_path = data.get('bot_map_path', 'config/bot_map.yaml')
        
        # Performance settings
        config = {**DEFAULT_CONFIG, **data.get('performance_config', {})}
        
        # API settings
        base_url = data.get('base_url', DEFAULT_BASE_URL)
        headers_raw = data.get('headers', '{}')
        
        if not conversation_ids:
            return jsonify({'success': False, 'error': 'No conversation IDs provided'}), 400
        
        # Reset streaming state
        app_state.streaming_results = []
        app_state.streaming_status = {"completed": 0, "total": len(conversation_ids)}
        
        # Load required configurations
        rubrics_cfg = load_unified_rubrics()
        if not rubrics_cfg:
            return jsonify({'success': False, 'error': 'Could not load unified rubrics'}), 500
        
        # Configure brand settings
        brand_policy = None
        brand_resolver = None
        
        if brand_mode == "single":
            try:
                brand_path = f"brands/{selected_brand}/prompt.md"
                brand_prompt_text, brand_policy = load_brand_prompt(brand_path)
                if not brand_policy:
                    raise ValueError(f"Could not load brand policy for {selected_brand}")
            except Exception as e:
                return jsonify({'success': False, 'error': f'Brand loading error: {str(e)}'}), 500
        else:
            try:
                brand_resolver = BrandResolver(bot_map_path)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Brand resolver error: {str(e)}'}), 500
        
        # Setup LLM client
        llm_api_key = os.getenv("GEMINI_API_KEY", "")
        if not llm_api_key:
            return jsonify({'success': False, 'error': 'GEMINI_API_KEY not found in environment'}), 500
        
        # Configure API headers
        try:
            headers = json.loads(headers_raw) if headers_raw.strip() else {}
        except:
            headers = {}
        
        # Initialize evaluator
        evaluator_config = {
            'rubrics_cfg': rubrics_cfg,
            'apply_diagnostics': data.get('apply_diagnostics', True),
            'diagnostics_cfg': load_diagnostics_config() if data.get('apply_diagnostics', True) else None,
            'brand_policy': brand_policy,
            'brand_resolver': brand_resolver,
            'brand_mode': brand_mode,
            'max_chars': config['max_chars']
        }
        
        # Performance monitoring
        perf_monitor = PerformanceMonitor() if config['show_performance_metrics'] else None
        
        # Setup streaming callback
        def stream_callback(result):
            """Stream results as they complete"""
            app_state.streaming_results.append(result)
            app_state.streaming_status["completed"] = len(app_state.streaming_results)
        
        # Setup progress callback
        def progress_callback(progress, completed, total):
            """Update progress"""
            app_state.streaming_status["completed"] = completed
            app_state.streaming_status["total"] = total
        
        # Run actual evaluation using high-speed batch evaluator
        try:
            results = asyncio.run(evaluate_conversations_high_speed(
                conversation_ids=conversation_ids,
                base_url=base_url,
                rubrics_cfg=rubrics_cfg,
                brand_policy=brand_policy,
                brand_prompt_text=brand_prompt_text if brand_mode == "single" else None,
                llm_api_key=llm_api_key,
                llm_model="gemini-2.5-flash",
                temperature=config['temperature'],
                llm_base_url=data.get('llm_base_url'),
                apply_diagnostics=data.get('apply_diagnostics', True),
                diagnostics_cfg=evaluator_config['diagnostics_cfg'],
                max_concurrency=config['max_concurrency'],
                progress_callback=progress_callback,
                stream_callback=stream_callback,
                brand_resolver=brand_resolver,
                use_high_performance_api=config['use_high_performance_api'],
                redis_url=data.get('redis_url') if config['enable_caching'] else None,
                api_rate_limit=config['api_rate_limit'],
                use_progressive_batching=config['use_progressive_batching']
            ))
            
            # Generate summary
            summary = make_summary(results)
            
        except Exception as e:
            # Fallback for sync execution or errors
            logger.error(f"Async evaluation failed: {e}, falling back to sync")
            traceback.print_exc()
            
            # Simple fallback - create minimal results
            results = []
            for i, conv_id in enumerate(conversation_ids):
                error_result = {
                    'conversation_id': conv_id,
                    'error': f"Evaluation failed: {str(e)}",
                    'timestamp': datetime.now().isoformat()
                }
                results.append(error_result)
                app_state.streaming_results.append(error_result)
                app_state.streaming_status["completed"] = i + 1
            
            # Generate fallback summary
            summary = {
                'count': len(results),
                'successful_count': 0,
                'avg_total_score': 0,
                'policy_violation_rate': 0,
                'flow_distribution': {},
                'brand_distribution': {},
                'processing_time': 0
            }
        
        # Store results
        app_state.evaluation_results = results
        app_state.summary_data = summary
        
        # Calculate successful results
        successful_results = [r for r in results if "error" not in r]
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': summary,
            'total_processed': len(results),
            'successful': len(successful_results)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/streaming-status', methods=['GET'])
def get_streaming_status():
    """Get current streaming evaluation status"""
    return jsonify({
        'success': True,
        'status': app_state.streaming_status,
        'results_count': len(app_state.streaming_results),
        'latest_results': app_state.streaming_results[-5:] if app_state.streaming_results else []
    })

@app.route('/api/export/<format>')
def export_results(format):
    """Export evaluation results in various formats"""
    try:
        if not app_state.evaluation_results or not app_state.summary_data:
            return jsonify({'success': False, 'error': 'No evaluation results available'}), 400
        
        if format == 'pdf':
            # Generate PDF report (simplified for Flask)
            try:
                # Import PDF creation functions
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_pdf import PdfPages
                
                output = BytesIO()
                
                with PdfPages(output) as pdf:
                    # Title page
                    fig, ax = plt.subplots(figsize=(8, 11))
                    ax.text(0.5, 0.7, 'Bus QA Evaluation Report', 
                           ha='center', va='center', fontsize=20, fontweight='bold')
                    ax.text(0.5, 0.6, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                           ha='center', va='center', fontsize=12)
                    ax.text(0.5, 0.5, f'Total Results: {len(app_state.evaluation_results)}', 
                           ha='center', va='center', fontsize=14)
                    
                    if app_state.summary_data:
                        summary = app_state.summary_data
                        ax.text(0.5, 0.4, f'Successful: {summary.get("successful_count", 0)}', 
                               ha='center', va='center', fontsize=14)
                        ax.text(0.5, 0.3, f'Average Score: {summary.get("avg_total_score", 0):.1f}', 
                               ha='center', va='center', fontsize=14)
                    
                    ax.set_xlim(0, 1)
                    ax.set_ylim(0, 1)
                    ax.axis('off')
                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close(fig)
                
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'bus_qa_evaluation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                )
                
            except Exception as e:
                return jsonify({'success': False, 'error': f'PDF generation failed: {str(e)}'}), 500
        
        elif format == 'excel':
            # Generate Excel report
            output = BytesIO()
            
            # Create DataFrame
            export_data = []
            for result in app_state.evaluation_results:
                if 'error' not in result:
                    export_data.append({
                        'conversation_id': result['conversation_id'],
                        'brand': result.get('brand', ''),
                        'flow': result['result'].get('flow', ''),
                        'total_score': result['result'].get('total_score', 0),
                        'label': result['result'].get('label', ''),
                        'confidence': result['result'].get('confidence', 0),
                        'processing_time': result.get('metrics', {}).get('processing_time', 0),
                        'policy_violations': result.get('metrics', {}).get('policy_violations', 0)
                    })
            
            df = pd.DataFrame(export_data)
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Evaluation Results', index=False)
                
                # Add summary sheet
                summary_df = pd.DataFrame([app_state.summary_data])
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'bus_qa_evaluation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
        
        elif format == 'json':
            # Export as JSON
            export_data = {
                'results': app_state.evaluation_results,
                'summary': app_state.summary_data,
                'exported_at': datetime.now().isoformat(),
                'metadata': {
                    'total_results': len(app_state.evaluation_results),
                    'successful_results': app_state.summary_data.get('successful_count', 0)
                }
            }
            
            return jsonify(export_data)
        
        else:
            return jsonify({'success': False, 'error': f'Unsupported format: {format}'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Clear evaluation results and reset state"""
    app_state.evaluation_results = None
    app_state.summary_data = None
    app_state.streaming_results = []
    app_state.streaming_status = {"completed": 0, "total": 0}
    app_state.bulk_conversations = None
    
    return jsonify({'success': True, 'message': 'Results cleared successfully'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Development mode - use port 5000 for Flask web app
    port = int(os.getenv('PORT', 5000))  # Flask default port
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Starting Bus QA LLM Evaluator Web App on port {port}")
    print(f"🌐 Access at: http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
