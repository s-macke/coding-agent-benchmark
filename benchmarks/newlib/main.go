package main

import "C"
import (
	"fmt"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/giorgisio/goav/avcodec"
	"github.com/giorgisio/goav/avutil"
	"github.com/giorgisio/goav/swscale"
	"image"
	"image/png"
	"log"
	"net"
	"net/http"
	"os"
	"sync"
	"unsafe"

	//	"github.com/syohex/go-aalib"
	"github.com/NYTimes/gziphandler"
)
import "github.com/giorgisio/goav/avformat"

type ffmpegvideo struct {
	filename      string
	videostreamid int

	pFormatContext *avformat.Context
	pCodecCtx      *avcodec.Context
	pCodecCtxOrig  *avformat.CodecContext
	pCodec         *avcodec.Codec

	targetwidth, targetheight int
	pFrame                    *avutil.Frame

	pFrameRGB *avutil.Frame
	buffer    unsafe.Pointer
	avp       *avcodec.Picture

	swsCtx *swscale.Context

	packet *avcodec.Packet
}

func (video *ffmpegvideo) Init(filename string, targetwidth, targetheight int) {
	video.filename = filename
	video.targetwidth = targetwidth
	video.targetheight = targetheight

	// Open video file
	video.pFormatContext = avformat.AvformatAllocContext()
	if avformat.AvformatOpenInput(&video.pFormatContext, video.filename, nil, nil) != 0 {
		fmt.Printf("Unable to open file %s\n", video.filename)
		os.Exit(1)
	}

	// Retrieve stream information
	if video.pFormatContext.AvformatFindStreamInfo(nil) < 0 {
		fmt.Println("Couldn't find stream information")
		os.Exit(1)
	}

	// Dump information about file onto standard error
	fmt.Println("--------------------------------------------------------------")
	video.pFormatContext.AvDumpFormat(0, os.Args[1], 0)
	fmt.Println("--------------------------------------------------------------")

	video.GetCodecCtx()

	// Allocate video frame
	video.pFrame = avutil.AvFrameAlloc()

	// Allocate an AVFrame structure
	video.pFrameRGB = avutil.AvFrameAlloc()
	if video.pFrameRGB == nil {
		fmt.Println("Unable to allocate RGB Frame")
		os.Exit(1)
	}

	// Determine required buffer size and allocate buffer
	numBytes := uintptr(avcodec.AvpictureGetSize(avcodec.AV_PIX_FMT_RGBA, video.targetwidth, video.targetheight))
	video.buffer = avutil.AvMalloc(numBytes)

	// Assign appropriate parts of buffer to image planes in pFrameRGB
	// Note that pFrameRGB is an AVFrame, but AVFrame is a superset
	// of AVPicture
	video.avp = (*avcodec.Picture)(unsafe.Pointer(video.pFrameRGB))
	video.avp.AvpictureFill((*uint8)(video.buffer), avcodec.AV_PIX_FMT_RGBA, video.targetwidth, video.targetheight)

	// initialize SWS context for software scaling
	video.swsCtx = swscale.SwsGetcontext(
		video.pCodecCtx.Width(),
		video.pCodecCtx.Height(),
		(swscale.PixelFormat)(video.pCodecCtx.PixFmt()),
		video.targetwidth,
		video.targetheight,
		avcodec.AV_PIX_FMT_RGBA,
		avcodec.SWS_BILINEAR,
		nil,
		nil,
		nil,
	)

	video.packet = avcodec.AvPacketAlloc()
}

func (video *ffmpegvideo) Free() {

	// Free the RGB image
	avutil.AvFree(video.buffer)
	avutil.AvFrameFree(video.pFrameRGB)

	// Free the YUV frame
	avutil.AvFrameFree(video.pFrame)

	// Close the codecs
	video.pCodecCtx.AvcodecClose()
	(*avcodec.Context)(unsafe.Pointer(video.pCodecCtxOrig)).AvcodecClose()

	// Close the video file
	video.pFormatContext.AvformatCloseInput()
	// Stop after saving frames of first video straem
}

func (video *ffmpegvideo) GetCodecCtx() {
	video.videostreamid = -1
	// Find the first video stream
	for i := 0; i < int(video.pFormatContext.NbStreams()); i++ {
		if video.pFormatContext.Streams()[i].CodecParameters().AvCodecGetType() == avformat.AVMEDIA_TYPE_VIDEO {
			video.videostreamid = i
		}
	}

	if video.videostreamid == -1 {
		fmt.Println("Didn't find a video stream")
		os.Exit(1)
	}

	// Get a pointer to the codec context for the video stream
	video.pCodecCtxOrig = video.pFormatContext.Streams()[video.videostreamid].Codec()
	// Find the decoder for the video stream
	video.pCodec = avcodec.AvcodecFindDecoder(avcodec.CodecId(video.pCodecCtxOrig.GetCodecId()))
	if video.pCodec == nil {
		fmt.Println("Unsupported codec!")
		os.Exit(1)
	}
	// Copy context
	video.pCodecCtx = video.pCodec.AvcodecAllocContext3()
	if video.pCodecCtx.AvcodecCopyContext((*avcodec.Context)(unsafe.Pointer(video.pCodecCtxOrig))) != 0 {
		fmt.Println("Couldn't copy codec context")
		os.Exit(1)
	}

	// Open codec
	if video.pCodecCtx.AvcodecOpen2(video.pCodec, nil) < 0 {
		fmt.Println("Could not open codec")
		os.Exit(1)
	}
}

func (video *ffmpegvideo) ReceiveNextFrame() int {

	response := video.pCodecCtx.AvcodecReceiveFrame((*avcodec.Frame)(unsafe.Pointer(video.pFrame)))
	//fmt.Println("V1:", response)
	if response == 0 {
		return 0
	}
	video.packet.AvFreePacket()

	//if response == avutil.AvErrorEAGAIN || response == avutil.AvErrorEOF {
	if response == avutil.AvErrorEOF {
		fmt.Printf("Stream end: %s\n", avutil.ErrorFromCode(response))
		os.Exit(1)
	} else if response == -11 { // EAGAIN
	} else if response < 0 {
		fmt.Println(response)
		fmt.Printf("Error while receiving a frame from the decoder: %s\n", avutil.ErrorFromCode(response))
		return response
	}

	for {
		response = video.pFormatContext.AvReadFrame(video.packet)
		if response < 0 {
			fmt.Println(response)
			fmt.Printf("Error while receiving a frame from the decoder: %s\n", avutil.ErrorFromCode(response))
			return response
		}

		// Is this a packet from the video stream?
		if video.packet.StreamIndex() == video.videostreamid {
			// Decode video frame
			response := video.pCodecCtx.AvcodecSendPacket(video.packet)

			if response < 0 {
				fmt.Printf("Error while sending a packet to the decoder: %s\n", avutil.ErrorFromCode(response))
			}
			for response >= 0 {
				response = video.pCodecCtx.AvcodecReceiveFrame((*avcodec.Frame)(unsafe.Pointer(video.pFrame)))

				//if response == avutil.AvErrorEAGAIN || response == avutil.AvErrorEOF {
				if response == -11 || response == avutil.AvErrorEOF {
					break
				} else if response < 0 {
					fmt.Println(response)
					fmt.Printf("Error while receiving a frame from the decoder: %s\n", avutil.ErrorFromCode(response))
					return response
				}
				return 0
			}
		}
		// Free the packet that was allocated by av_read_frame
		video.packet.AvFreePacket()
	}

}

func (video *ffmpegvideo) Scale() {
	swscale.SwsScale2(
		video.swsCtx,
		avutil.Data(video.pFrame),
		avutil.Linesize(video.pFrame),
		0,
		video.pCodecCtx.Height(),
		avutil.Data(video.pFrameRGB),
		avutil.Linesize(video.pFrameRGB))
}

var lastTimestamp int64 = 0

func (video *ffmpegvideo) Wait() {
	timebase := video.pCodecCtx.AvCodecGetPktTimebase()
	rat := float32(timebase.Num()) / float32(timebase.Den()) * 1000. * 1000.

	currentTimestamp := avutil.GetBestEffortTimestamp(video.pFrame)
	//is->video_st->time_base

	if lastTimestamp > currentTimestamp {
		lastTimestamp = currentTimestamp
		return
	}

	if (currentTimestamp - lastTimestamp) > 200000 {
		lastTimestamp = currentTimestamp
		return
	}
	//fmt.Println((float32(currentTimestamp - lastTimestamp)) * rat)

	time.Sleep(time.Duration((float32(currentTimestamp-lastTimestamp))*rat) * time.Microsecond)
	lastTimestamp = currentTimestamp
}

func StoreImage(img image.Image) {
	// outputFile is a File type which satisfies Writer interface
	outputFile, err := os.Create("test.png")
	if err != nil {
		log.Fatal(err)
	}
	png.Encode(outputFile, img)
	outputFile.Close()
}

// -------------------------------------

var sharedText string
var framenumber int32
var condition *sync.Cond
var nconnections int64 = 0

func handleConnection(c net.Conn) {
	fmt.Printf("Serving %s\n", c.RemoteAddr().String())
	c.Write([]byte("\033[H\033[2J"))
	n := framenumber
	atomic.AddInt64(&nconnections, 1)
	defer atomic.AddInt64(&nconnections, -1)
	for {
		condition.L.Lock()
		for framenumber == n {
			condition.Wait()
		}
		n = framenumber
		condition.L.Unlock()
		c.Write([]byte(sharedText))
	}
	c.Close()
}

func StartServer() {
	PORT := ":" + "8081"
	l, err := net.Listen("tcp4", PORT)
	if err != nil {
		fmt.Println(err)
		return
	}
	defer l.Close()
	for {

		c, err := l.Accept()
		if err != nil {
			log.Fatal(err)
		}
		go handleConnection(c)
	}
}

// -------------------------------------

func handler(w http.ResponseWriter, r *http.Request) {

	w.Write([]byte("\033[H\033[2J"))
	n := framenumber
	atomic.AddInt64(&nconnections, 1)
	defer atomic.AddInt64(&nconnections, -1)

	for {
		condition.L.Lock()
		for framenumber == n {
			condition.Wait()
		}
		n = framenumber
		condition.L.Unlock()

		_, err := w.Write([]byte(sharedText))
		if err != nil {
			fmt.Println(err)
			return
		}

	}
}

// -------------------------------------

func ToText(img image.Image) string {
	var sb strings.Builder
	/*
		cColors := [16]int32{ 0x000000, 0x000080, 0x008000, 0x008080, 0x800000, 0x800080, 0x808000, 0xC0C0C0, 0x808080, 0x0000FF, 0x00FF00, 0x00FFFF, 0xFF0000, 0xFF00FF, 0xFFFF00, 0xFFFFFF }
		cTable := [16]color.RGBA{}
	*/
	//rList := [4]rune{'░', '▒', '▓', '█'} // 1/4, 2/4, 3/4, 4/4
	//char[] rList = new char[] { (char)9617, (char)9618, (char)9619, (char)9608 }; // 1/4, 2/4, 3/4, 4/4
	/*
		for index, element := range cColors {
			cTable[index] = color.RGBA{
				R: uint8(element >> 0),
				G: uint8(element >> 8),
				B: uint8(element >> 16),
				A: 0,
			}
		}
	*/
	//Color[] cTable = cColors.Select(x => Color.FromArgb(x)).ToArray();

	for j := 0; j < img.Bounds().Size().Y>>1; j++ {
		for i := 0; i < img.Bounds().Size().X>>1; i++ {
			rb, gb, bb, _ := img.At(i<<1, j<<1).RGBA()
			r := int((rb >> 8) & 0xFF)
			g := int((gb >> 8) & 0xFF)
			b := int((bb >> 8) & 0xFF)
			//sb.WriteString("\033[38;2;" + strconv.Itoa(r) +";"+ strconv.Itoa(g) + ";" + strconv.Itoa(b) + "m")

			r = (r) / 43
			g = (g) / 43
			b = (b) / 43
			sb.WriteString("\033[38;5;" + strconv.Itoa(16+r*36+g*6+b) + "m")

			rb, gb, bb, _ = img.At(i<<1, (j<<1)+1).RGBA()
			r = int((rb >> 8) & 0xFF)
			g = int((gb >> 8) & 0xFF)
			b = int((bb >> 8) & 0xFF)
			//sb.WriteString("\033[48;5;" + strconv.Itoa(r) +";"+ strconv.Itoa(g) + ";" + strconv.Itoa(b) + "m")
			r = (r) / 43
			g = (g) / 43
			b = (b) / 43
			sb.WriteString("\033[48;5;" + strconv.Itoa(16+r*36+g*6+b) + "m")

			sb.WriteRune('▀')
			/*
				bestHit := [4]int{ 0, 0, 4, 0xFFFFFFF };

				for rChar := len(rList); rChar > 0; rChar-- {
					for cFore := 0; cFore < len(cColors); cFore++ {
						for cBack := 0; cBack < len(cColors); cBack++ {
							R := (int(cTable[cFore].R)*rChar + int(cTable[cBack].R)*(len(rList)-rChar)) / len(rList);
							G := (int(cTable[cFore].G)*rChar + int(cTable[cBack].G)*(len(rList)-rChar)) / len(rList);
							B := (int(cTable[cFore].B)*rChar + int(cTable[cBack].B)*(len(rList)-rChar)) / len(rList);
							iScore := (r-R)*(r-R) + (g-G)*(g-G) + (b-B)*(b-B);
							if (!(rChar > 1 && rChar < 4 && iScore > 50000)) { // rule out too weird combinations
								if (iScore < bestHit[3]) {
									bestHit[3] = iScore; //Score
									bestHit[0] = cFore;  //ForeColor
									bestHit[1] = cBack;  //BackColor
									bestHit[2] = rChar;  //Symbol
								}
							}
						}
					}
				}


				cF := "3" + strconv.Itoa(bestHit[0])
				if (bestHit[0] > 7) {
					cF = "9" + strconv.Itoa(bestHit[0]-8)
				}

				cB := "4" + strconv.Itoa(bestHit[1])
				if (bestHit[1] > 7) {
					cF = "10" + strconv.Itoa(bestHit[1]-8)
				}

				sb.WriteString("\033[" + cF + ";" + cB + "m")
				sb.WriteRune(rList[bestHit[2]-1])

			*/
			/*
				Console.ForegroundColor = (ConsoleColor)bestHit[0];
				Console.BackgroundColor = (ConsoleColor)bestHit[1];
				Console.Write(rList[bestHit[2] - 1]);
			*/
			/*
				brightness := (r + g + b)/3
				if (brightness < 0x3000) {
					sb.WriteString(" ")
				} else
				if (brightness < 0x6000) {
					sb.WriteString("░")
				} else
				if (brightness < 0x9000) {
					sb.WriteString("▒")
				} else
				if (brightness < 0xC000) {
					sb.WriteString("▓")
				} else
				if (brightness < 0xF000) {
					sb.WriteString("█")
				}
			*/

		}
		sb.WriteString("\n")
	}

	return sb.String()
}

func DecodeVideo() {
	var video ffmpegvideo
	video.Init(os.Args[1], 50*4, 40*2)
	img := image.NewRGBA(image.Rect(0, 0, video.targetwidth, video.targetheight))
	//handle, _ := aalib.Init(video.targetwidth/2, video.targetheight/2, aalib.AA_NORMAL_MASK)

	for {
		//video.ReceiveNextFrame()
		response := video.ReceiveNextFrame()
		if response == avutil.AvErrorEOF {
			video.pFormatContext.AvformatSeekFile(video.videostreamid, 0, 0, 0, 0)
			continue
		}

		video.Scale()
		video.Wait()
		if nconnections <= 0 {
			time.Sleep(1 * time.Second)
		}
		//fmt.Println(nconnections)

		//fmt.Println("received frame")

		var data0 *uint8
		data0 = avutil.Data(video.pFrameRGB)[0]
		data := uintptr(unsafe.Pointer(data0))
		for i := 0; i < video.targetwidth*video.targetheight*4; i++ {
			img.Pix[i] = *(*uint8)(unsafe.Pointer(data + uintptr(i)))
		}
		str := ToText(img)

		//StoreImage(img)
		//handle.PutImage(img)
		//fmt.Println(handle.ImgWidth(), handle.ImgHeight())
		//fmt.Println(handle.ScrWidth(), handle.ScrHeight())
		//fmt.Println(video.targetwidth, video.targetheight)
		//handle.Render(nil, 0, 0, video.targetwidth, video.targetheight)
		//print("\033[H\033[2J")

		condition.L.Lock()
		//sharedText = "\033[;H" + handle.Text()
		sharedText = "\033[;H" + "\033[0m" + "Serving " + strconv.Itoa(int(nconnections)) + " connections. https://github.com/s-macke\n" + str
		framenumber++
		condition.Broadcast()
		condition.L.Unlock()
	}
	video.Free()
}

func main() {

	if len(os.Args) < 2 {
		fmt.Println("Please provide a movie file")
		os.Exit(1)
	}

	m := sync.Mutex{}
	condition = sync.NewCond(&m)

	//	go StartServer()

	withoutGz := http.HandlerFunc(handler)
	withGz := gziphandler.GzipHandler(withoutGz)
	go func() {
		log.Fatal(http.ListenAndServe(":12345", withGz))
	}()

	for {
		DecodeVideo()
	}

}

/*
func main() {
	//aalib.Init(100,100)
	//fmt.Println("Hello world")

	//filename := "sample.mp4"
	filename := "http://admin:admin@192.168.178.20:9981/stream/channelid/1843237503?ticket=D8887E8EB9A114B4E3BCABED4CA8FD005DB693CC&profile=pass"

	// Register all formats and codecs
	avformat.AvRegisterAll()

	ctx := avformat.AvformatAllocContext()

	// Open video file
	if avformat.AvformatOpenInput(&ctx, filename, nil, nil) != 0 {
		log.Println("Error: Couldn't open file.")
		return
	}

	// Retrieve stream information
	if ctx.AvformatFindStreamInfo(nil) < 0 {
		log.Println("Error: Couldn't find stream information.")

		// Close input file and free context
		ctx.AvformatCloseInput()
		return
	}
}
*/
