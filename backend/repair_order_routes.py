from flask import Blueprint, request, jsonify
from models import db, RepairOrder, RepairOrderPart, RepairOrderLabour
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from datetime import datetime
import json
from repair_order_inventory_utils import process_repair_order_parts, handle_repair_order_edit_inventory
from jwt_auth import login_required, role_required, admin_required

repair_order_bp = Blueprint('repair_order', __name__)

# Get all repair orders with optional status filter
@repair_order_bp.route('/repair-orders', methods=['GET'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_repair_orders(current_user=None):
    try:
        status = request.args.get('status')
        keyword = request.args.get('keyword')
        search_id = request.args.get('id')
        
        query = RepairOrder.query
        
        if status and status != 'all':
            query = query.filter(RepairOrder.current_status == status)
        
        # Search by ID
        if search_id:
            try:
                repair_order_id = int(search_id)
                query = query.filter(RepairOrder.id == repair_order_id)
            except ValueError:
                # If ID is not a valid integer, return empty result
                return jsonify({'repair_orders': []})
        
        # Search by keyword
        if keyword:
            keyword_filter = f"%{keyword}%"
            query = query.filter(
                db.or_(
                    RepairOrder.customer_name.ilike(keyword_filter),
                    RepairOrder.customer_phone.ilike(keyword_filter),
                    RepairOrder.customer_address.ilike(keyword_filter),
                    RepairOrder.customer_reg_no.ilike(keyword_filter),
                    RepairOrder.customer_made.ilike(keyword_filter),
                    RepairOrder.customer_vin.ilike(keyword_filter),
                    RepairOrder.customer_color.ilike(keyword_filter),
                    RepairOrder.customer_chasis.ilike(keyword_filter),
                    RepairOrder.problem_description.ilike(keyword_filter),
                    RepairOrder.worker_name.ilike(keyword_filter)
                )
            )
        
        # Use joinedload to fetch related data in one query (fixes N+1 problem)
        repair_orders = query.options(
            joinedload(RepairOrder.parts),
            joinedload(RepairOrder.labour)
        ).order_by(desc(RepairOrder.created_at)).all()
        
        result = []
        for ro in repair_orders:
            # Parts and labour are now already loaded via joinedload
            parts = ro.parts
            labour = ro.labour
            
            repair_order_data = {
                'id': ro.id,
                'customer_name': ro.customer_name,
                'customer_phone': ro.customer_phone,
                'customer_address': ro.customer_address,
                'customer_reg_no': ro.customer_reg_no,
                'customer_made': ro.customer_made,
                'customer_mileage': ro.customer_mileage,
                'customer_vin': ro.customer_vin,
                'customer_color': ro.customer_color,
                'customer_chasis': ro.customer_chasis,
                'problem_description': ro.problem_description,
                'diagnosis_plan': ro.diagnosis_plan,
                'worker_id': ro.worker_id,
                'worker_name': ro.worker_name,
                'current_status': ro.current_status,
                'status_timeline': json.loads(ro.status_timeline) if ro.status_timeline else {},
                'vehicle_condition': json.loads(ro.vehicle_condition) if ro.vehicle_condition else {},
                'notes': ro.notes,
                'created_at': ro.created_at.isoformat() if ro.created_at else None,
                'updated_at': ro.updated_at.isoformat() if ro.updated_at else None,
                'parts': [
                    {
                        'id': part.id,
                        'inventory_id': part.inventory_id,
                        'description': part.description,
                        'part_number': part.part_number,
                        'quantity': part.quantity,
                        'status': part.status
                    } for part in parts
                ],
                'labour': [
                    {
                        'id': labour_item.id,
                        'description': labour_item.description,
                        'status': labour_item.status
                    } for labour_item in labour
                ]
            }
            result.append(repair_order_data)
        
        return jsonify({'repair_orders': result})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get a specific repair order by ID
@repair_order_bp.route('/repair-orders/<int:repair_order_id>', methods=['GET'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_repair_order(repair_order_id, current_user=None):
    try:
        # Use joinedload to fetch related data in one query
        repair_order = RepairOrder.query.options(
            joinedload(RepairOrder.parts),
            joinedload(RepairOrder.labour)
        ).get(repair_order_id)
        
        if not repair_order:
            return jsonify({'error': 'Repair order not found'}), 404
        
        # Parts and labour are now already loaded via joinedload
        parts = repair_order.parts
        labour = repair_order.labour
        
        repair_order_data = {
            'id': repair_order.id,
            'customer_name': repair_order.customer_name,
            'customer_phone': repair_order.customer_phone,
            'customer_address': repair_order.customer_address,
            'customer_reg_no': repair_order.customer_reg_no,
            'customer_made': repair_order.customer_made,
            'customer_mileage': repair_order.customer_mileage,
            'customer_vin': repair_order.customer_vin,
            'customer_color': repair_order.customer_color,
            'customer_chasis': repair_order.customer_chasis,
            'problem_description': repair_order.problem_description,
            'diagnosis_plan': repair_order.diagnosis_plan,
            'worker_id': repair_order.worker_id,
            'worker_name': repair_order.worker_name,
            'current_status': repair_order.current_status,
            'status_timeline': json.loads(repair_order.status_timeline) if repair_order.status_timeline else {},
            'vehicle_condition': json.loads(repair_order.vehicle_condition) if repair_order.vehicle_condition else {},
            'notes': repair_order.notes,
            'created_at': repair_order.created_at.isoformat() if repair_order.created_at else None,
            'updated_at': repair_order.updated_at.isoformat() if repair_order.updated_at else None,
            'parts': [
                {
                    'id': part.id,
                    'inventory_id': part.inventory_id,
                    'description': part.description,
                    'part_number': part.part_number,
                    'quantity': part.quantity,
                    'status': part.status
                } for part in parts
            ],
            'labour': [
                {
                    'id': labour_item.id,
                    'description': labour_item.description,
                    'status': labour_item.status
                } for labour_item in labour
            ]
        }
        
        return jsonify(repair_order_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Create a new repair order
@repair_order_bp.route('/repair-orders', methods=['POST'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def create_repair_order(current_user=None):
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('customer_name'):
            return jsonify({'error': 'Customer name is required'}), 400
        
        # Create repair order
        repair_order = RepairOrder(
            customer_name=data['customer_name'],
            customer_phone=data.get('customer_phone', ''),
            customer_address=data.get('customer_address', ''),
            customer_reg_no=data.get('customer_reg_no', ''),
            customer_made=data.get('customer_made', ''),
            customer_mileage=data.get('customer_mileage', ''),
            customer_vin=data.get('customer_vin', ''),
            customer_color=data.get('customer_color', ''),
            customer_chasis=data.get('customer_chasis', ''),
            problem_description=data.get('problem_description', ''),
            worker_id=int(data.get('worker_id')) if data.get('worker_id') and data.get('worker_id').strip() else None,
            worker_name=data.get('worker_name', ''),
            current_status='received',
        )
        
        db.session.add(repair_order)
        db.session.flush()  # Get the ID
        
        # Process parts
        if data.get('parts'):
            success, processed_parts, inventory_errors = process_repair_order_parts(data['parts'])
            
            if not success:
                db.session.rollback()
                return jsonify({'error': 'Failed to process parts', 'details': inventory_errors}), 400
            
            for part_data in processed_parts:
                part = RepairOrderPart(
                    repair_order_id=repair_order.id,
                    description=part_data['description'],
                    quantity=part_data['quantity'],
                    inventory_id=part_data.get('inventory_id'),
                    part_number=part_data.get('part_number', ''),
                    status=part_data.get('status', 'pending')
                )
                db.session.add(part)
        
        # Process labour
        if data.get('labour'):
            for labour_data in data['labour']:
                labour = RepairOrderLabour(
                    repair_order_id=repair_order.id,
                    description=labour_data['description'],
                    status=labour_data.get('status', 'pending')
                )
                db.session.add(labour)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Repair order created successfully',
            'repair_order_id': repair_order.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Update repair order status
@repair_order_bp.route('/repair-orders/<int:repair_order_id>/status', methods=['PUT'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def update_repair_order_status(repair_order_id, current_user=None):
    try:
        repair_order = RepairOrder.query.get(repair_order_id)
        
        if not repair_order:
            return jsonify({'error': 'Repair order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        # Update current status
        repair_order.current_status = new_status
        
        # Update status timeline
        timeline = json.loads(repair_order.status_timeline) if repair_order.status_timeline else {}
        
        # Parse timestamp safely
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = parsed_timestamp.strftime('%H:%M')
        except (ValueError, AttributeError):
            # Fallback to current time if timestamp parsing fails
            parsed_timestamp = datetime.now()
            time_str = parsed_timestamp.strftime('%H:%M')
            timestamp = parsed_timestamp.isoformat()
        
        timeline[new_status] = {
            'date': timestamp,
            'time': time_str
        }
        repair_order.status_timeline = json.dumps(timeline)
        
        repair_order.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Status updated successfully',
            'current_status': new_status,
            'status_timeline': timeline
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Update repair order
@repair_order_bp.route('/repair-orders/<int:repair_order_id>', methods=['PUT'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def update_repair_order(repair_order_id, current_user=None):
    try:
        repair_order = RepairOrder.query.get(repair_order_id)
        
        if not repair_order:
            return jsonify({'error': 'Repair order not found'}), 404
        
        data = request.get_json()
        
        # Update basic information (only if provided and not None)
        if 'customer_name' in data and data['customer_name'] is not None:
            repair_order.customer_name = data['customer_name']
        if 'customer_phone' in data and data['customer_phone'] is not None:
            repair_order.customer_phone = data['customer_phone']
        if 'customer_address' in data and data['customer_address'] is not None:
            repair_order.customer_address = data['customer_address']
        if 'customer_reg_no' in data and data['customer_reg_no'] is not None:
            repair_order.customer_reg_no = data['customer_reg_no']
        if 'customer_made' in data and data['customer_made'] is not None:
            repair_order.customer_made = data['customer_made']
        if 'customer_mileage' in data and data['customer_mileage'] is not None:
            repair_order.customer_mileage = data['customer_mileage']
        if 'customer_vin' in data and data['customer_vin'] is not None:
            repair_order.customer_vin = data['customer_vin']
        if 'customer_color' in data and data['customer_color'] is not None:
            repair_order.customer_color = data['customer_color']
        if 'customer_chasis' in data and data['customer_chasis'] is not None:
            repair_order.customer_chasis = data['customer_chasis']
        if 'problem_description' in data:
            repair_order.problem_description = data['problem_description']
        if 'worker_id' in data:
            repair_order.worker_id = int(data['worker_id']) if data['worker_id'] and str(data['worker_id']).strip() else None
        if 'worker_name' in data:
            repair_order.worker_name = data['worker_name']
        if 'diagnosis_plan' in data:
            repair_order.diagnosis_plan = data['diagnosis_plan']
        if 'vehicle_condition' in data:
            repair_order.vehicle_condition = json.dumps(data['vehicle_condition'])
        if 'notes' in data:
            repair_order.notes = data['notes']
        
        repair_order.updated_at = datetime.now()
        
        # Update parts if provided
        if 'parts' in data:
            # Get current parts for inventory comparison
            current_parts = RepairOrderPart.query.filter_by(repair_order_id=repair_order_id).all()
            current_parts_data = []
            for part in current_parts:
                current_parts_data.append({
                    'id': part.id,
                    'inventory_id': part.inventory_id,
                    'description': part.description,
                    'part_number': part.part_number,
                    'quantity': part.quantity,
                    'status': part.status
                })
            
            # Handle inventory changes
            success, inventory_errors = handle_repair_order_edit_inventory(current_parts_data, data['parts'])
            
            if not success:
                db.session.rollback()
                return jsonify({'error': 'Failed to process inventory changes', 'inventory_errors': inventory_errors}), 400
            
            # Delete existing parts
            RepairOrderPart.query.filter_by(repair_order_id=repair_order_id).delete()
            
            # Add new parts
            for part_data in data['parts']:
                part = RepairOrderPart(
                    repair_order_id=repair_order_id,
                    inventory_id=part_data.get('inventory_id'),
                    description=part_data.get('description'),
                    part_number=part_data.get('part_number'),
                    quantity=part_data.get('quantity', 1),
                    status=part_data.get('status', 'pending')
                )
                db.session.add(part)
            
            # Add inventory warnings if any
            if inventory_errors:
                response_data = {'message': 'Repair order updated successfully with some inventory warnings', 'inventory_warnings': inventory_errors}
            else:
                response_data = {'message': 'Repair order updated successfully'}
        
        # Update labour if provided
        if 'labour' in data:
            # Delete existing labour
            RepairOrderLabour.query.filter_by(repair_order_id=repair_order_id).delete()
            
            # Add new labour
            for labour_data in data['labour']:
                labour = RepairOrderLabour(
                    repair_order_id=repair_order_id,
                    description=labour_data.get('description'),
                    status=labour_data.get('status', 'pending')
                )
                db.session.add(labour)
        
        db.session.commit()
        
        # Return appropriate response based on inventory warnings
        if 'response_data' in locals():
            return jsonify(response_data)
        else:
            return jsonify({'message': 'Repair order updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Delete repair order
@repair_order_bp.route('/repair-orders/<int:repair_order_id>/delete', methods=['DELETE'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def delete_repair_order(repair_order_id, current_user=None):
    try:
        repair_order = RepairOrder.query.get(repair_order_id)
        
        if not repair_order:
            return jsonify({'error': 'Repair order not found'}), 404
        
        # Get parts before deletion to restore inventory
        parts_to_restore = RepairOrderPart.query.filter_by(repair_order_id=repair_order_id).all()
        
        # Restore inventory for all parts
        for part in parts_to_restore:
            if part.inventory_id and part.quantity > 0:
                from models import Inventory
                inventory_item = Inventory.query.get(part.inventory_id)
                if inventory_item:
                    inventory_item.quantity += part.quantity
        
        # Delete related parts and labour
        RepairOrderPart.query.filter_by(repair_order_id=repair_order_id).delete()
        RepairOrderLabour.query.filter_by(repair_order_id=repair_order_id).delete()
        
        # Delete the repair order
        db.session.delete(repair_order)
        db.session.commit()
        
        return jsonify({'message': 'Repair order deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Update specific part status
@repair_order_bp.route('/repair-orders/<int:repair_order_id>/parts/<int:part_id>/status', methods=['PUT'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def update_part_status(repair_order_id, part_id, current_user=None):
    try:
        part = RepairOrderPart.query.filter_by(
            repair_order_id=repair_order_id, 
            id=part_id
        ).first()
        
        if not part:
            return jsonify({'error': 'Part not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        part.status = new_status
        db.session.commit()
        
        return jsonify({'message': 'Part status updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Update specific labour status
@repair_order_bp.route('/repair-orders/<int:repair_order_id>/labour/<int:labour_id>/status', methods=['PUT'])
@login_required
@role_required(['admin', 'accountant', 'inventory_manager'])
def update_labour_status(repair_order_id, labour_id, current_user=None):
    try:
        labour = RepairOrderLabour.query.filter_by(
            repair_order_id=repair_order_id, 
            id=labour_id
        ).first()
        
        if not labour:
            return jsonify({'error': 'Labour item not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'error': 'Status is required'}), 400
        
        labour.status = new_status
        db.session.commit()
        
        return jsonify({'message': 'Labour status updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500 