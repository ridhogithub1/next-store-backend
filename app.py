from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://rr6093225_db_user:SlhRyLgrH5VzNMvs@cluster0.ihxeqhh.mongodb.net/?appName=Cluster0')
DATABASE_NAME = "dropship_db"
COLLECTION_NAME = "orders"

# Initialize MongoDB client
try:
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    orders_collection = db[COLLECTION_NAME]
    
    # Test connection
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "Dropship API is running",
        "endpoints": {
            "/api/orders": "POST - Create new order",
            "/api/orders/<order_id>": "GET - Get order by ID",
            "/api/orders/all": "GET - Get all orders"
        }
    })

@app.route('/api/orders', methods=['POST'])
def create_order():
    """
    Create a new order and save to MongoDB
    """
    try:
        # Get data from request
        order_data = request.get_json()
        
        # Validate required fields
        required_fields = ['nama', 'alamat', 'telepon', 'produk', 'productId', 
                          'jumlah', 'totalHarga', 'metodePembayaran']
        
        for field in required_fields:
            if field not in order_data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
        
        # Add server timestamp and order ID
        order_data['createdAt'] = datetime.utcnow()
        order_data['updatedAt'] = datetime.utcnow()
        order_data['status'] = 'pending'  # Default status
        
        # Generate order ID (you can use the timestamp from frontend or generate new one)
        if 'orderId' not in order_data:
            order_data['orderId'] = str(int(datetime.utcnow().timestamp() * 1000))
        
        # Insert to MongoDB
        result = orders_collection.insert_one(order_data)
        
        # Get the inserted document
        inserted_order = orders_collection.find_one({"_id": result.inserted_id})
        
        # Convert ObjectId to string for JSON serialization
        inserted_order['_id'] = str(inserted_order['_id'])
        
        print(f"✅ Order created successfully: {order_data['orderId']}")
        print(f"📦 Order details: {order_data}")
        
        return jsonify({
            "status": "success",
            "message": "Order created successfully",
            "data": inserted_order
        }), 201
        
    except Exception as e:
        print(f"❌ Error creating order: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """
    Get order by order ID
    """
    try:
        order = orders_collection.find_one({"orderId": order_id})
        
        if not order:
            return jsonify({
                "status": "error",
                "message": "Order not found"
            }), 404
        
        # Convert ObjectId to string
        order['_id'] = str(order['_id'])
        
        return jsonify({
            "status": "success",
            "data": order
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting order: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/orders/all', methods=['GET'])
def get_all_orders():
    """
    Get all orders with optional filters
    """
    try:
        # Get query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # Build query
        query = {}
        if status:
            query['status'] = status
        
        # Get orders from MongoDB
        orders = list(orders_collection.find(query)
                     .sort('createdAt', -1)  # Sort by newest first
                     .skip(skip)
                     .limit(limit))
        
        # Convert ObjectId to string
        for order in orders:
            order['_id'] = str(order['_id'])
        
        # Get total count
        total_count = orders_collection.count_documents(query)
        
        return jsonify({
            "status": "success",
            "data": orders,
            "total": total_count,
            "limit": limit,
            "skip": skip
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting orders: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/orders/<order_id>', methods=['PUT'])
def update_order_status(order_id):
    """
    Update order status
    """
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({
                "status": "error",
                "message": "Status is required"
            }), 400
        
        # Valid statuses
        valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({
                "status": "error",
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }), 400
        
        # Update order
        result = orders_collection.update_one(
            {"orderId": order_id},
            {
                "$set": {
                    "status": new_status,
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({
                "status": "error",
                "message": "Order not found or status unchanged"
            }), 404
        
        # Get updated order
        updated_order = orders_collection.find_one({"orderId": order_id})
        updated_order['_id'] = str(updated_order['_id'])
        
        return jsonify({
            "status": "success",
            "message": "Order status updated",
            "data": updated_order
        }), 200
        
    except Exception as e:
        print(f"❌ Error updating order: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Get order statistics
    """
    try:
        total_orders = orders_collection.count_documents({})
        pending_orders = orders_collection.count_documents({"status": "pending"})
        processing_orders = orders_collection.count_documents({"status": "processing"})
        completed_orders = orders_collection.count_documents({"status": "delivered"})
        
        # Calculate total revenue
        pipeline = [
            {"$group": {
                "_id": None,
                "totalRevenue": {"$sum": "$totalHarga"}
            }}
        ]
        revenue_result = list(orders_collection.aggregate(pipeline))
        total_revenue = revenue_result[0]['totalRevenue'] if revenue_result else 0
        
        return jsonify({
            "status": "success",
            "data": {
                "totalOrders": total_orders,
                "pendingOrders": pending_orders,
                "processingOrders": processing_orders,
                "completedOrders": completed_orders,
                "totalRevenue": total_revenue
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)