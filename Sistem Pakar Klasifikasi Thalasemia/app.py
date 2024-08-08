from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import datetime
import json
import numpy as np

app = Flask(__name__)
app.secret_key = '12345'

# Inisialisasi DataFrame global
user_df = pd.read_excel('pakar/data.xlsx', sheet_name='pengguna')
gejala_df = pd.read_excel('pakar/data.xlsx', sheet_name='gejala')
bobot_df = pd.read_excel('pakar/data.xlsx', sheet_name='bobot')
persentase_df = pd.read_excel('pakar/data.xlsx', sheet_name='persentase')
penyakit_df = pd.read_excel('pakar/data.xlsx', sheet_name='penyakit')
solusi_df = pd.read_excel('pakar/data.xlsx', sheet_name='solusi')
kasus_df = pd.read_excel('pakar/data.xlsx', sheet_name='kasus')


def check_credentials(username, password):
    user = user_df[(user_df['username'] == username) & (user_df['password'] == password)]
    if not user.empty:
        return user.iloc[0]['level']
    return None


@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        level = check_credentials(username, password)
        if level is not None:
            session['username'] = username
            session['level'] = int(level)
            if level == 0:
                return redirect('/user')
            elif level == 1:
                return redirect('/pakar')
        else:
            error = 'Invalid username or password. Please try again.'
    return render_template('login.html', error=error)


@app.route('/user')
def user():
    gejala = gejala_df.to_dict(orient='records')
    bobot = bobot_df.to_dict(orient='records')
    return render_template('user.html', gejala=gejala, bobot=bobot)


@app.route('/pakar')
def pakar():
    gejala = gejala_df.to_dict(orient='records')
    bobot = bobot_df.to_dict(orient='records')
    return render_template('pakar-diagnosa.html', gejala=gejala, bobot=bobot)


@app.route('/logout')
def logout():
    session.clear()
    return render_template('login.html')


@app.route('/route_rbr', methods=['POST'])
def route_rbr():
    global kasus_df  # Memastikan bahwa kita mengakses dan memodifikasi variabel global kasus_df

    nama = request.form.get('nama')
    jenis_kelamin = request.form.get('jenis_kelamin')
    usia = request.form.get('usia')

    gejala_selected = {}
    for i in range(1, 12):  # Sesuaikan dengan jumlah gejala yang dikirimkan
        gejala_key = f'gejala{i}'
        bobot_key = f'bobot{i}'

        if gejala_key in request.form and bobot_key in request.form:
            gejala_selected[request.form[gejala_key]] = float(request.form[bobot_key])

    total_gejala = len(gejala_selected)
    total_bobot = sum(gejala_selected.values())
    persentase = round((total_bobot / total_gejala) * 100,2)

    if persentase <= 50:
        kode_penyakit = 'P001'
        kode_solusi = 'S001'
    else:
        kode_penyakit = 'P002'
        kode_solusi = 'S002'

    penyakit = penyakit_df.loc[penyakit_df['Id_Penyakit'] == kode_penyakit, 'Penyakit'].values[0]
    solusi = solusi_df.loc[solusi_df['Id_Solusi'] == kode_solusi, 'Solusi_Penyakit'].values[0]

    tanggal = datetime.datetime.now().strftime('%Y-%m-%d')

    # Menentukan ID Kasus Baru
    if kasus_df.empty:
        new_id = 'K001'
    else:
        last_id = kasus_df['ID'].iloc[-1]
        new_id_number = int(last_id[1:]) + 1
        new_id = f'K{new_id_number:03d}'

    # Menambah data pasien ke DataFrame
    new_case = pd.DataFrame([{
        'ID': new_id,
        'Nama': nama,
        'Jenis Kelamin': jenis_kelamin,
        'Usia': usia,
        'Tanggal': tanggal,
        'Gejala': json.dumps(gejala_selected),  # Simpan gejala sebagai JSON string
        'Penyakit': kode_penyakit,
        'Solusi': kode_solusi,
        'Persentase': persentase,
        'Metode': 'RBR'
    }])

    kasus_df = pd.concat([kasus_df, new_case], ignore_index=True)

    # Simpan DataFrame ke Excel
    with pd.ExcelWriter('pakar/data.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        kasus_df.to_excel(writer, sheet_name='kasus', index=False)

    return redirect(url_for('route_rbr_result', nama=nama, jenis_kelamin=jenis_kelamin, usia=usia,
                            penyakit=penyakit, solusi=solusi, tanggal=tanggal, persentase=persentase))


@app.route('/hasil-diagnosa-rbr')
def route_rbr_result():
    nama = request.args.get('nama')
    jenis_kelamin = request.args.get('jenis_kelamin')
    usia = request.args.get('usia')
    penyakit = request.args.get('penyakit')
    solusi = request.args.get('solusi')
    tanggal = request.args.get('tanggal')
    persentase = request.args.get('persentase')

    return render_template('hasil-diagnosa-rbr.html', nama=nama, jenis_kelamin=jenis_kelamin, usia=usia,
                           penyakit=penyakit, solusi=solusi, tanggal=tanggal, persentase=persentase)


@app.route('/route_cbr', methods=['POST'])
def route_cbr():
    global kasus_df

    if request.method == 'POST':
        nama = request.form.get('nama')
        jenis_kelamin = request.form.get('jenis_kelamin')
        usia = request.form.get('usia')

        gejala_selected = {}
        for i in range(1, 12):  # Sesuaikan dengan jumlah gejala yang dikirimkan
            gejala_key = f'gejala{i}'
            bobot_key = f'bobot{i}'

            if gejala_key in request.form and bobot_key in request.form:
                gejala_selected[request.form[gejala_key]] = float(request.form[bobot_key])

        if kasus_df.empty:
            # Jika belum ada data kasus, tampilkan pesan peringatan
            return  redirect(url_for('cbr_no_case'))

        # Mengumpulkan semua gejala yang ada dalam semua kasus
        all_gejala = set(gejala_selected.keys())
        for idx, row in kasus_df.iterrows():
            gejala_kasus = json.loads(row['Gejala'])
            all_gejala.update(gejala_kasus.keys())

        # Perhitungan CBR
        closest_case = None
        closest_distance = float('inf')

        for idx, row in kasus_df.iterrows():
            gejala_kasus = json.loads(row['Gejala'])

            # Mengisi nilai gejala yang tidak ada dengan nol
            gejala_selected_vector = np.array([gejala_selected.get(gejala, 0) for gejala in all_gejala])
            gejala_kasus_vector = np.array([gejala_kasus.get(gejala, 0) for gejala in all_gejala])

            distance = np.linalg.norm(gejala_selected_vector - gejala_kasus_vector)

            if distance < closest_distance:
                closest_distance = distance
                closest_case = row

        if closest_case is not None:
            kode_penyakit = closest_case['Penyakit']
            penyakit = penyakit_df.loc[penyakit_df['Id_Penyakit'] == kode_penyakit, 'Penyakit'].values[0]
            solusi = closest_case['Solusi']
            gejala_lama = json.loads(closest_case['Gejala'])  # Mengonversi string -> JSON (dictionary)
            pasien_lama_nama = closest_case['Nama']
            pasien_lama_jenis_kelamin = closest_case['Jenis Kelamin']
            pasien_lama_usia = closest_case['Usia']
            pasien_lama_tanggal = datetime.datetime.strptime(closest_case['Tanggal'], '%Y-%m-%d')
            pasien_lama_tanggal = pasien_lama_tanggal.strftime('%Y-%m-%d')

            # Filter gejala_selected dan gejala_lama berdasarkan bobot
            filtered_gejala_selected = {gejala: bobot for gejala, bobot in gejala_selected.items()}
            filtered_gejala_lama = {gejala: bobot for gejala, bobot in gejala_lama.items()}

            # Menghitung similarity sebagai persentase
            max_distance = np.sqrt(len(filtered_gejala_selected))  # Jarak maksimum jika semua bobot = 1
            similarity_percent = round((1 - closest_distance / max_distance) * 100, 2)
        else:
            kode_penyakit = 'Unknown'
            penyakit = 'Unknown'
            solusi = 'No solution found'
            gejala_lama = {}  # Default kosong jika tidak ada kasus terdekat ditemukan
            pasien_lama_nama = 'Unknown'
            pasien_lama_jenis_kelamin = 'Unknown'
            pasien_lama_usia = 'Unknown'
            pasien_lama_tanggal = 'Unknown'
            filtered_gejala_selected = {}
            filtered_gejala_lama = {}
            similarity_percent = 0

        tanggal = datetime.datetime.now().strftime('%Y-%m-%d')

        # Menentukan ID Kasus Baru
        if kasus_df.empty:
            new_id = 'K001'
        else:
            last_id = kasus_df['ID'].iloc[-1]
            new_id_number = int(last_id[1:]) + 1
            new_id = f'K{new_id_number:03d}'

        # Menambah data kasus ke DataFrame kasus_df
        new_case = pd.DataFrame([{
            'ID': new_id,
            'Nama': nama,
            'Jenis Kelamin': jenis_kelamin,
            'Usia': usia,
            'Tanggal': tanggal,
            'Gejala': json.dumps(filtered_gejala_selected),  # Simpan gejala sebagai JSON string
            'Penyakit': kode_penyakit,
            'Solusi': solusi,
            'Persentase': similarity_percent,
            'Metode': 'CBR'
        }])

        kasus_df = pd.concat([kasus_df, new_case], ignore_index=True)

        # Simpan DataFrame kasus_df ke Excel
        with pd.ExcelWriter('pakar/data.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            kasus_df.to_excel(writer, sheet_name='kasus', index=False)

        return redirect(url_for('route_cbr_result', nama=nama, jenis_kelamin=jenis_kelamin, usia=usia,
                                penyakit=penyakit, solusi=solusi, tanggal=tanggal,
                                gejala_baru=json.dumps(filtered_gejala_selected),
                                gejala_lama=json.dumps(filtered_gejala_lama), similarity=similarity_percent,
                                pasien_lama_nama=pasien_lama_nama, pasien_lama_jenis_kelamin=pasien_lama_jenis_kelamin,
                                pasien_lama_usia=pasien_lama_usia, pasien_lama_tanggal=pasien_lama_tanggal))

    return render_template('proses-diagnosa-cbr.html')

@app.route('/cbr-no-case')
def cbr_no_case():
    return render_template('no-case.html', error='Tidak ada data kasus sebelumnya. Metode CBR tpyak dapat dijalankan.')


@app.route('/hasil-diagnosa-cbr')
def route_cbr_result():
    nama = request.args.get('nama')
    jenis_kelamin = request.args.get('jenis_kelamin')
    usia = request.args.get('usia')
    penyakit = request.args.get('penyakit')
    solusi = request.args.get('solusi')
    tanggal = request.args.get('tanggal')
    gejala_baru = json.loads(request.args.get('gejala_baru'))
    gejala_lama = json.loads(request.args.get('gejala_lama'))
    similarity = request.args.get('similarity')
    pasien_lama_nama = request.args.get('pasien_lama_nama')
    pasien_lama_jenis_kelamin = request.args.get('pasien_lama_jenis_kelamin')
    pasien_lama_usia = request.args.get('pasien_lama_usia')
    pasien_lama_tanggal = request.args.get('pasien_lama_tanggal')
    return render_template('proses-diagnosa-cbr.html', nama=nama, jenis_kelamin=jenis_kelamin, usia=usia,
                           penyakit=penyakit, solusi=solusi, tanggal=tanggal, gejala_baru=gejala_baru,
                           gejala_lama=gejala_lama, similarity=similarity,
                           pasien_lama_nama=pasien_lama_nama, pasien_lama_jenis_kelamin=pasien_lama_jenis_kelamin,
                           pasien_lama_usia=pasien_lama_usia, pasien_lama_tanggal=pasien_lama_tanggal)


@app.route('/hasil_cbr', methods=['POST'])
def hasil_cbr():
    tanggal = request.form.get('tanggal')
    nama = request.form.get('nama')
    jenis_kelamin = request.form.get('jenis_kelamin')
    usia = request.form.get('usia')
    penyakit = request.form.get('penyakit')
    solusi = request.form.get('solusi')

    solusi = solusi_df.loc[solusi_df['Id_Solusi'] == solusi, 'Solusi_Penyakit'].values[0]

    return render_template('hasil-diagnosa-cbr.html', tanggal=tanggal, nama=nama, jenis_kelamin=jenis_kelamin,
                           solusi=solusi, usia=usia, penyakit=penyakit)

@app.route('/riwayat-kasus')
def riwayat_kasus():
    # Ambil data kasus dari DataFrame
    data_kasus = kasus_df.to_dict(orient='records')
    return render_template('riwayat-kasus.html', data_kasus=data_kasus)

@app.route('/hapus-kasus/<string:id>', methods=['POST'])
def hapus_kasus(id):
    global kasus_df

    kasus_df = kasus_df[kasus_df['ID'] != id]  # Hapus baris dengan ID kasus yang sesuai

    # Simpan DataFrame ke dalam file Excel setelah menghapus
    with pd.ExcelWriter('pakar/data.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        kasus_df.to_excel(writer, sheet_name='kasus', index=False)

    return redirect(url_for('riwayat_kasus'))

@app.route('/exit')
def exit():
    if 'level' in session:
        level = session['level']
        if level == 0:
            return redirect('/user')
        elif level == 1:
            return redirect('/pakar')
    return redirect('/')


@app.route('/gejala')
def gejala():
    return render_template('pakar-gejala.html', gejala=gejala_df.to_dict('records'))

@app.route('/tambah-gejala', methods=['GET', 'POST'])
def tambah_gejala():
    global gejala_df
    if request.method == 'POST':
        id_gejala = 'G' + str(len(gejala_df) + 1).zfill(3)
        nama_gejala = request.form['nama_gejala']
        pertanyaan_gejala = request.form['pertanyaan_gejala']
        new_gejala = pd.DataFrame([{'Id_gejala': id_gejala, 'Nama_Gejala': nama_gejala, 'pertanyaan_gejala': pertanyaan_gejala}])
        gejala_df = pd.concat([gejala_df, new_gejala], ignore_index=True)

        # Simpan DataFrame ke Excel
        with pd.ExcelWriter('pakar/data.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            gejala_df.to_excel(writer, sheet_name='gejala', index=False)

        return redirect(url_for('gejala'))
    return render_template('tambah-gejala.html')

@app.route('/hapus-gejala/<id_gejala>', methods=['POST'])
def hapus_gejala(id_gejala):
    global gejala_df
    gejala_df = gejala_df[gejala_df.Id_gejala != id_gejala]

    # Simpan DataFrame ke Excel
    with pd.ExcelWriter('pakar/data.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        gejala_df.to_excel(writer, sheet_name='gejala', index=False)

    return redirect(url_for('gejala'))


if __name__ == '__main__':
    app.run(debug=True)
