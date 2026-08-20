import geopy.distance
from database import db

class AddressProcessor:
    
    @staticmethod
    def get_coordinates(postcode):
        """
        Get coordinates from postcode (using mock data)
        """
        # Mock coordinates for testing
        mock_coords = {
            'ML3 8BL': (55.7713, -4.0540),  # Hamilton
            'E1 6AN': (51.5074, -0.1278),   # London
            'B1 1AA': (52.4862, -1.8904),   # Birmingham
            'M1 1AE': (53.4808, -2.2426),   # Manchester
        }
        return mock_coords.get(postcode, (55.7713, -4.0540))
    
    @staticmethod
    async def find_nearest_warehouse(postcode, carrier):
        """
        Find nearest warehouse based on postcode
        """
        # Get coordinates of delivery postcode
        delivery_coords = AddressProcessor.get_coordinates(postcode)
        
        # Get all warehouses from database
        async with db.pool.acquire() as conn:
            warehouses = await conn.fetch(
                "SELECT * FROM warehouses WHERE carrier = $1 OR carrier = 'All'",
                carrier
            )
        
        if not warehouses:
            print("⚠️ No warehouses found in database. Using mock warehouse.")
            # Return mock warehouse
            return {
                'name': '3PL Hub London',
                'address': '123 Industrial Estate, London',
                'postcode': 'E1 6AN',
                'latitude': 51.5074,
                'longitude': -0.1278
            }
        
        # Find nearest warehouse
        nearest = None
        min_distance = float('inf')
        
        for warehouse in warehouses:
            warehouse_coords = (warehouse['latitude'], warehouse['longitude'])
            distance = geopy.distance.distance(delivery_coords, warehouse_coords).km
            
            if distance < min_distance:
                min_distance = distance
                nearest = warehouse
        
        print(f"✅ Nearest warehouse: {nearest['name']} (Distance: {min_distance:.2f} km)")
        return nearest
    
    @staticmethod
    def format_address_for_carrier(warehouse, carrier):
        """
        Format warehouse address according to carrier requirements
        """
        formats = {
            'Royal Mail': {
                'building_name': warehouse['name'],
                'street': warehouse['address'].split(',')[0].strip(),
                'city': warehouse['address'].split(',')[1].strip() if ',' in warehouse['address'] else 'London',
                'postcode': warehouse['postcode']
            },
            'DPD': {
                'company_name': warehouse['name'],
                'address': warehouse['address'],
                'postcode': warehouse['postcode']
            },
            'UPS': {
                'company': warehouse['name'],
                'address1': warehouse['address'],
                'city': 'London',
                'postcode': warehouse['postcode']
            }
        }
        
        return formats.get(carrier, formats['Royal Mail'])