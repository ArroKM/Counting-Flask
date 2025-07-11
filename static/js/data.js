$(document).ready(function () {
  setInterval(updateClock, 1000);
  setInterval(getData, 10000);
  updateClock();
  getData();
});

function getData() {
  const zone = document.body.dataset.zone; // pastikan <body data-zone="merah"> misalnya
  const endpoint = zone === "merah" ? "/api/merah" : "/api/data";

  $.get(endpoint, function (response) {
    if (response.offline) {
      $("#offline-alert").show();  // Tampilkan alert
      $("#totalin").text("-");
      $("#totalout").text("-");
      $("#totalcur").text("-");
      $("#dept-table").html(`<tr><td colspan="4" class="text-center text-danger">Data tidak tersedia</td></tr>`);
      return;
    }

    $("#offline-alert").hide();  // Sembunyikan alert jika sebelumnya muncul

    $("#totalin").text(response.totalin);
    $("#totalout").text(response.totalout);
    $("#totalcur").text(response.totalcur);

    let html = '';
    response.data.forEach(dept => {
      html += `
        <tr>
          <td class="text-left bolded"><strong>${dept.dept}</strong></td>
          <td class="bolded"><strong>${dept.in}</strong></td>
          <td class="bolded"><strong>${dept.out}</strong></td>
          <td class="bolded"><strong>${dept.cur}</strong></td>
        </tr>
      `;
    });
    $("#dept-table").html(html);
  }).fail(function () {
    // Jika AJAX gagal (misalnya koneksi putus), juga tampilkan alert
    $("#offline-alert").show();
    $("#totalin").text("-");
    $("#totalout").text("-");
    $("#totalcur").text("-");
    $("#dept-table").html(`<tr><td colspan="4" class="text-center text-danger">Tidak dapat terhubung ke server</td></tr>`);
  });
}


function updateClock() {
  const now = new Date();
  const offset = (now.getTimezoneOffset() === 0) ? 7 * 3600000 : 0;
  now.setTime(now.getTime() + offset);

  const jam = now.getHours().toString().padStart(2, '0');
  const menit = now.getMinutes().toString().padStart(2, '0');
  const detik = now.getSeconds().toString().padStart(2, '0');

  const hariArray = ["Minggu,", "Senin,", "Selasa,", "Rabu,", "Kamis,", "Jum'at,", "Sabtu,"];
  const bulanArray = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                      "Juli", "Agustus", "September", "Oktober", "Nopember", "Desember"];

  $("#jam").text(jam);
  $("#menit").text(menit);
  $("#detik").text(detik);
  $("#tanggalwaktu").text(`${hariArray[now.getDay()]} ${now.getDate()} ${bulanArray[now.getMonth()]} ${now.getFullYear()}`);
}
