import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from mongoengine import connect, Document, StringField, EmailField, DateTimeField, ReferenceField
import datetime
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message

app = Flask(__name__)

# Configuración de la clave secreta para Flask (necesario para flash y sesiones)
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_segura_y_larga_para_sena_app'

# Configuración para la subida de archivos
UPLOAD_FOLDER = './uploads/' # Carpeta donde se guardarán los PDFs
ALLOWED_EXTENSIONS = {'pdf'} # Extensiones de archivo permitidas
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurarse de que la carpeta de subidas exista al iniciar la aplicación
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'mariadelprivera@gmail.com' # <--- ¡CAMBIA ESTO! Tu dirección de correo DEDICADA para la aplicación
app.config['MAIL_PASSWORD'] = 'gkleyricvurawonl' # <--- ¡CAMBIA ESTO! La contraseña de aplicación generada por Google
app.config['MAIL_DEFAULT_SENDER'] = 'mariadelprivera@gmail.com' # El remitente por defecto, generalmente el mismo que MAIL_USERNAME

mail = Mail(app) # Inicializa Flask-Mail

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # La vista a la que redirigir si se requiere login

# Configuración de la conexión a MongoDB
connect(db='GUIASDB', host='localhost', port=27017)

# --- Modelos de Datos ---

# Modelo para las Regionales del SENA
class Regional(Document):
    nombre_regional = StringField(required=True, unique=True)
    meta = {'collection': 'regionales'}

# Modelo para los Programas de Formación
class ProgramaFormacion(Document):
    nombre_programa = StringField(required=True, unique=True)
    meta = {'collection': 'programas_formacion'}

# Modelo para los Instructores, ahora heredando de UserMixin para Flask-Login
class Instructor(UserMixin, Document):
    nombre_completo = StringField(required=True)
    correo_electronico = EmailField(required=True, unique=True)
    regional = ReferenceField(Regional, required=True)
    usuario = StringField(required=True, unique=True)
    contrasena = StringField(required=True)
    meta = {'collection': 'instructores'}

    # Flask-Login necesita este método para obtener el ID del usuario
    def get_id(self):
        return str(self.id)

# Modelo para las Guías de Aprendizaje
class GuiaAprendizaje(Document):
    nombre_guia = StringField(required=True)
    descripcion = StringField(required=True)
    programa_formacion = ReferenceField(ProgramaFormacion, required=True)
    nombre_documento_pdf = StringField(required=True) # Guardará el nombre del archivo en el sistema de archivos
    fecha_publicacion = DateTimeField(default=datetime.datetime.now)
    instructor = ReferenceField(Instructor, required=True)
    meta = {'collection': 'guias_aprendizaje'}

# --- Funciones de Utilidad ---

# Función para validar extensiones de archivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Función para precargar datos iniciales (Regionales y Programas de Formación) si no existen
def precargar_datos_iniciales():
    print("Verificando y precargando datos iniciales...")
    # Regionales
    regionales_a_insertar = [
        "Cauca", "Huila", "Antioquia", "Valle", "Nariño", "Cundinamarca",
        "Atlántico", "Santander", "Boyacá", "Risaralda"
    ]
    for reg_nombre in regionales_a_insertar:
        if not Regional.objects(nombre_regional=reg_nombre).first():
            Regional(nombre_regional=reg_nombre).save()
            print(f"Regional '{reg_nombre}' precargada.")

    # Programas de Formación
    programas_a_insertar = [
        "Desarrollo de Software", "Multimedia", "Inteligencia Artificial",
        "Analítica de Datos", "Construcción", "Contabilidad", "Diseño Gráfico",
        "Electrónica", "Mecánica Industrial"
    ]
    for prog_nombre in programas_a_insertar:
        if not ProgramaFormacion.objects(nombre_programa=prog_nombre).first():
            ProgramaFormacion(nombre_programa=prog_nombre).save()
            print(f"Programa de Formación '{prog_nombre}' precargado.")
    print("Precarga de datos iniciales completada.")

# Asegurarse de que los datos se precarguen al inicio de la aplicación
with app.app_context():
    precargar_datos_iniciales()

# --- Callbacks de Flask-Login ---

# Este callback es usado por Flask-Login para recargar el objeto de usuario desde el ID de usuario almacenado en la sesión
@login_manager.user_loader
def load_user(user_id):
    return Instructor.objects(id=user_id).first()

# --- Rutas de la Aplicación ---

# Ruta principal: redirige al dashboard si el usuario está logueado, de lo contrario al login
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Ruta para mostrar el formulario de registro de instructores
@app.route('/registro_instructor')
def mostrar_registro_instructor():
    regionales = Regional.objects()
    return render_template('registro_instructor.html', regionales=regionales)

# Ruta para procesar el envío del formulario de registro de instructores
@app.route('/registrar_instructor', methods=['POST'])
def registrar_instructor():
    if request.method == 'POST':
        nombre_completo = request.form['nombre_completo']
        correo_electronico = request.form['correo_electronico']
        regional_id = request.form['regional']

        try:
            if Instructor.objects(correo_electronico=correo_electronico).first():
                flash('El correo electrónico ya está registrado.', 'error')
                regionales = Regional.objects()
                return render_template('registro_instructor.html', regionales=regionales)

            regional_obj = Regional.objects.get(id=regional_id)

            usuario_generado = correo_electronico.split('@')[0] + str(random.randint(100, 999))
            contrasena_generada = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=10))

            contrasena_hasheada = generate_password_hash(contrasena_generada)

            nuevo_instructor = Instructor(
                nombre_completo=nombre_completo,
                correo_electronico=correo_electronico,
                regional=regional_obj,
                usuario=usuario_generado,
                contrasena=contrasena_hasheada
            )
            nuevo_instructor.save()

            # --- Lógica de Envío de Correo Electrónico ---
            try:
                msg = Message('Datos de Acceso a la Aplicación SENA',
                              sender=app.config['MAIL_DEFAULT_SENDER'],
                              recipients=[correo_electronico])
                msg.body = (f"Hola {nombre_completo},\n\n"
                            f"Has sido registrado exitosamente en la aplicación de Guías de Aprendizaje del SENA.\n\n"
                            f"Tus datos de acceso son:\n"
                            f"Usuario: {usuario_generado}\n"
                            f"Contraseña: {contrasena_generada}\n\n"
                            f"Por favor, inicia sesión en: {url_for('login', _external=True)}\n\n"
                            f"¡Bienvenido!\n"
                            f"Equipo SENA")
                mail.send(msg)
                mensaje_final_flash = (f"Instructor '{nombre_completo}' registrado con éxito. "
                                       f"Datos de acceso enviados a {correo_electronico}.")
                flash(mensaje_final_flash, 'success')
            except Exception as mail_e:
                print(f"Error al enviar correo: {mail_e}")
                mensaje_final_flash = (f"Instructor '{nombre_completo}' registrado con éxito. "
                                       f"Usuario: {usuario_generado}, Contraseña: {contrasena_generada}. "
                                       f"¡ATENCIÓN!: No se pudo enviar el correo de datos de acceso. Error: {mail_e}")
                flash(mensaje_final_flash, 'warning') # Usamos 'warning' para indicar un éxito parcial

            return redirect(url_for('login'))

        except Exception as e:
            print(f"Error al registrar instructor: {e}")
            flash(f'Ocurrió un error al registrar el instructor: {e}', 'error')
            regionales = Regional.objects()
            return render_template('registro_instructor.html', regionales=regionales)

    return redirect(url_for('mostrar_registro_instructor'))

# Ruta para mostrar el formulario de inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']

        instructor = Instructor.objects(usuario=usuario).first()

        if instructor and check_password_hash(instructor.contrasena, contrasena):
            login_user(instructor)
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
            return render_template('login.html')
    return render_template('login.html')

# Ruta del dashboard (requiere que el usuario esté logueado)
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', current_user=current_user)

# Ruta para cerrar sesión
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))

# Ruta para mostrar el formulario de subida de guías
@app.route('/subir_guia', methods=['GET'])
@login_required
def mostrar_subir_guia():
    programas = ProgramaFormacion.objects()
    return render_template('subir_guia.html', programas=programas)

# Ruta para procesar la subida de guías
@app.route('/subir_guia', methods=['POST'])
@login_required
def subir_guia():
    if request.method == 'POST':
        nombre_guia = request.form['nombre_guia']
        descripcion = request.form['descripcion']
        programa_formacion_id = request.form['programa_formacion']

        if 'documento_pdf' not in request.files:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.url)

        file = request.files['documento_pdf']

        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            try:
                programa_obj = ProgramaFormacion.objects.get(id=programa_formacion_id)

                nueva_guia = GuiaAprendizaje(
                    nombre_guia=nombre_guia,
                    descripcion=descripcion,
                    programa_formacion=programa_obj,
                    nombre_documento_pdf=filename,
                    instructor=current_user
                )
                nueva_guia.save()

                flash('Guía de aprendizaje subida con éxito.', 'success')
                return redirect(url_for('dashboard'))

            except Exception as e:
                print(f"Error al guardar la guía en la DB: {e}")
                flash(f'Ocurrió un error al guardar la guía en la base de datos: {e}', 'error')
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect(request.url)
        else:
            flash('Tipo de archivo no permitido. Solo se aceptan PDFs.', 'error')
            return redirect(request.url)

    return redirect(url_for('dashboard'))

# Ruta para mostrar el listado de guías de aprendizaje
@app.route('/listar_guias')
@login_required # Solo usuarios logueados pueden ver el listado
def listar_guias():
    try:
        # Corrección: Simplificamos select_related para adaptarnos a la limitación de argumentos.
        # Solo cargamos 'instructor' y 'programa_formacion' directamente.
        # 'instructor.regional' se cargará de forma perezosa (lazy-loading) cuando se acceda en el template.
        guias = GuiaAprendizaje.objects().order_by('-fecha_publicacion')


        # Añadimos un print para depurar, como habíamos acordado
        print("\n--- Guías recuperadas de la DB ---")
        if guias:
            for guia in guias:
                print(f"ID: {guia.id}, Nombre: {guia.nombre_guia}")
                print(f"  Instructor: {guia.instructor.nombre_completo if guia.instructor else 'N/A'}")
                print(f"  Programa: {guia.programa_formacion.nombre_programa if guia.programa_formacion else 'N/A'}")
                print(f"  Regional: {guia.instructor.regional.nombre_regional if guia.instructor and guia.instructor.regional else 'N/A'}")
                print(f"  PDF: {guia.nombre_documento_pdf}")
        else:
            print("No se encontraron guías en la base de datos.")
        print("-----------------------------------\n")

        return render_template('listar_guias.html', guias=guias)
    except Exception as e:
        # Captura cualquier error que ocurra durante la consulta o renderizado
        print(f"Error en la ruta /listar_guias: {e}")
        flash(f"Ocurrió un error al cargar las guías: {e}", 'error')
        return redirect(url_for('dashboard')) # Redirige al dashboard en caso de error

# Ruta para servir los archivos PDF
@app.route('/uploads/<filename>')
@login_required # Solo usuarios logueados pueden acceder a los PDFs
def descargar_pdf(filename):
    # Asegúrate de que el archivo exista y sea seguro antes de servirlo
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Bloque para ejecutar la aplicación Flask
if __name__ == '__main__':
    app.run(debug=True) # debug=True para ver errores detallados