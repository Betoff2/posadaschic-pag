from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import sqlite3
import os

# Configuración
app = Flask(__name__)
CORS(app)  # Habilitar CORS

DATABASE = 'products.db'
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurarse de que la carpeta static/images existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  price REAL NOT NULL,
                  category TEXT NOT NULL,
                  image TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS product_sizes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  product_id INTEGER,
                  size TEXT NOT NULL,
                  stock INTEGER NOT NULL DEFAULT 0,
                  FOREIGN KEY (product_id) REFERENCES products(id))''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    db = get_db()
    products = db.execute('''
        SELECT p.*, GROUP_CONCAT(ps.size || ':' || ps.stock) as sizes 
        FROM products p 
        LEFT JOIN product_sizes ps ON p.id = ps.product_id 
        GROUP BY p.id
    ''').fetchall()
    db.close()
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Gestión de Productos</title>
            <link rel="stylesheet" href="/static/css/styles.css">
        </head>
        <body>
        <h1>Gestión de Productos</h1>
        
        <!-- Formulario para añadir productos -->
        <form action="/add_product" method="post" enctype="multipart/form-data">
            <input type="text" name="name" placeholder="Nombre del producto" required>
            <input type="number" name="price" placeholder="Precio" step="0.01" required>
            <select name="category" required>
                <option value="Pantalones">Pantalones</option>
                <option value="Remeras">Remeras</option>
                <option value="Buzos">Buzos</option>
            </select>
            <div id="sizes">
                <h3>Talles disponibles:</h3>
                <div class="size-input">
                    <select name="sizes[]">
                        <option value="S">S</option>
                        <option value="M">M</option>
                        <option value="L">L</option>
                        <option value="XL">XL</option>
                        <option value="42">42</option>
                        <option value="44">44</option>
                        <option value="46">46</option>
                        <option value="48">48</option>
                    </select>
                    <input type="number" name="stock[]" placeholder="Stock para este talle" required>
                </div>
            </div>
            <button type="button" onclick="addSizeInput()">Agregar otro talle</button>
            <input type="file" name="image" accept="image/*">
            <button type="submit">Añadir Producto</button>
        </form>

        <!-- Tabla de productos existentes -->
        <h2>Productos Existentes</h2>
        <table>
            <tr>
                <th>Nombre</th>
                <th>Precio</th>
                <th>Categoría</th>
                <th>Imagen</th>
                <th>Talles y Stock</th>
                <th>Acciones</th>
            </tr>
            {% for product in products %}
            <tr>
                <td>{{ product['name'] }}</td>
                <td>${{ product['price'] }}</td>
                <td>{{ product['category'] }}</td>
                <td><img src="{{ product['image'] }}" alt="Imagen de {{ product['name'] }}" width="50"></td>
                <td>{{ product['sizes'] }}</td>
                <td>
                    <a href="/edit_product/{{ product['id'] }}">Editar</a> |
                    <a href="/delete_product/{{ product['id'] }}" onclick="return confirm('¿Está seguro de eliminar este producto?')">Eliminar</a>
                </td>
            </tr>
            {% endfor %}
        </table>

        <script>
        function addSizeInput() {
            const sizesDiv = document.getElementById('sizes');
            const newSize = document.createElement('div');
            newSize.className = 'size-input';
            newSize.innerHTML = `
                <select name="sizes[]">
                    <option value="S">S</option>
                    <option value="M">M</option>
                    <option value="L">L</option>
                    <option value="XL">XL</option>
                    <option value="42">42</option>
                    <option value="44">44</option>
                    <option value="46">46</option>
                    <option value="48">48</option>
                </select>
                <input type="number" name="stock[]" placeholder="Stock para este talle" required>
            `;
            sizesDiv.appendChild(newSize);
        }
        </script>
        </body>
        </html>
    ''', products=products)
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'image' not in request.files:
        return 'No se envió ninguna imagen', 400
    
    file = request.files['image']
    if file.filename == '':
        return 'No se seleccionó ninguna imagen', 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            file.save(filepath)
        except Exception as e:
            print(f"Error al guardar la imagen: {e}")
            return 'Ocurrió un error al guardar la imagen', 500
        
        try:
            db = get_db()
            db.execute('INSERT INTO products (name, price, category, image) VALUES (?, ?, ?, ?)',
                       (request.form['name'], request.form['price'], request.form['category'], filepath))
            db.commit()
            
            product_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            sizes = request.form.getlist('sizes[]')
            stock_values = request.form.getlist('stock[]')
            for size, stock in zip(sizes, stock_values):
                db.execute('INSERT INTO product_sizes (product_id, size, stock) VALUES (?, ?, ?)',
                           (product_id, size, int(stock)))
            db.commit()
            db.close()
        except sqlite3.Error as e:
            print(f"Error al agregar el producto: {e}")
            return 'Ocurrió un error al agregar el producto', 500
        
        return redirect(url_for('index'))
    return 'Tipo de archivo no válido', 400
@app.route('/get_products', methods=['GET'])
def get_products():
    try:
        db = get_db()
        products = db.execute('''
            SELECT p.*, GROUP_CONCAT(ps.size || ':' || ps.stock) as sizes
            FROM products p
            LEFT JOIN product_sizes ps ON p.id = ps.product_id
            GROUP BY p.id
        ''').fetchall()
        db.close()
        return jsonify([dict(row) for row in products])
    except sqlite3.Error as e:
        print(f"Error al obtener los productos: {e}")
        return "Ocurrió un error al obtener los productos. Por favor, inténtalo de nuevo más tarde.", 500
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    db = get_db()
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        category = request.form['category']
        
        db.execute('UPDATE products SET name = ?, price = ?, category = ? WHERE id = ?',
                   (name, price, category, id))
        
        sizes = request.form.getlist('sizes[]')
        stock_values = request.form.getlist('stock[]')
        db.execute('DELETE FROM product_sizes WHERE product_id = ?', (id,))
        for size, stock in zip(sizes, stock_values):
            db.execute('INSERT INTO product_sizes (product_id, size, stock) VALUES (?, ?, ?)',
                       (id, size, int(stock)))
        
        db.commit()
        db.close()
        
        return redirect(url_for('index'))
    
    product = db.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
    sizes = db.execute('SELECT * FROM product_sizes WHERE product_id = ?', (id,)).fetchall()
    db.close()
    
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="es">
        <head><title>Editar Producto</title></head>
        <body>
            <h1>Editar Producto</h1>
            <form method="post">
                <input type="text" name="name" value="{{ product['name'] }}" required>
                <input type="number" name="price" value="{{ product['price'] }}" step="0.01" required>
                <select name="category">
                    <option value="Pantalones" {% if product['category'] == 'Pantalones' %}selected{% endif %}>Pantalones</option>
                    <option value="Remeras" {% if product['category'] == 'Remeras' %}selected{% endif %}>Remeras</option>
                    <option value="Buzos" {% if product['category'] == 'Buzos' %}selected{% endif %}>Buzos</option>
                </select>
                <div id="sizes">
                    {% for size in sizes %}
                    <div class="size-input">
                        <select name="sizes[]">
                            <option value="S" {% if size['size'] == 'S' %}selected{% endif %}>S</option>
                            <option value="M" {% if size['size'] == 'M' %}selected{% endif %}>M</option>
                            <option value="L" {% if size['size'] == 'L' %}selected{% endif %}>L</option>
                            <option value="XL" {% if size['size'] == 'XL' %}selected{% endif %}>XL</option>
                            <option value="42" {% if size['size'] == '42' %}selected{% endif %}>42</option>
                            <option value="44" {% if size['size'] == '44' %}selected{% endif %}>44</option>
                            <option value="46" {% if size['size'] == '46' %}selected{% endif %}>46</option>
                            <option value="48" {% if size['size'] == '48' %}selected{% endif %}>48</option>
                        </select>
                        <input type="number" name="stock[]" value="{{ size['stock'] }}" required>
                    </div>
                    {% endfor %}
                </div>
                <button type="button" onclick="addSizeInput()">Agregar otro talle</button>
                <button type="submit">Guardar Cambios</button>
            </form>
            <script>
            function addSizeInput() {
                const sizesDiv = document.getElementById('sizes');
                const newSize = document.createElement('div');
                newSize.className = 'size-input';
                newSize.innerHTML = `
                    <select name="sizes[]">
                        <option value="S">S</option>
                        <option value="M">M</option>
                        <option value="L">L</option>
                        <option value="XL">XL</option>
                        <option value="42">42</option>
                        <option value="44">44</option>
                        <option value="46">46</option>
                        <option value="48">48</option>
                    </select>
                    <input type="number" name="stock[]" placeholder="Stock para este talle" required>
                `;
                sizesDiv.appendChild(newSize);
            }
            </script>
        </body>
        </html>
    ''', product=product, sizes=sizes)

@app.route('/delete_product/<int:id>')
def delete_product(id):
    db = get_db()
    db.execute('DELETE FROM products WHERE id = ?', (id,))
    db.execute('DELETE FROM product_sizes WHERE product_id = ?', (id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
